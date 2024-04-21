import cv2
import numpy as np
import sys
import blend_modes
import json

try:
	from kkpmx_image_lib import DisplayWithAspectRatio, DisplayWithAspectRatio_f
	import kkpmx_image_lib as imglib
except ImportError as eee:
	from . import kkpmx_image_lib as imglib
	DisplayWithAspectRatio = imglib.DisplayWithAspectRatio
	DisplayWithAspectRatio_f = imglib.DisplayWithAspectRatio_f

argLen = len(sys.argv)
if (argLen < 2):
	print("Must have at least 2 arguments")
	exit()

#-------------
imgMain   = sys.argv[1] ## MainTex.png
imgMask   = sys.argv[2] ## overtex.png
#-------------
data = {};
if (argLen > 3): data = imglib.TryLoadJson(sys.argv[3], False, True)
nip          = data.get("nip", 1.0)        ## Scales texture a bit
nipsize_def  = 0.6677417
nipsize      = data.get("size", nipsize_def) ## Increases Factor for nip (== Areola Size)
details      = data.get("showinfo", False)
overcolor    = data.get("color",  [1, 0.7771759, 0.7261904, 1])
legacy       = data.get("legacy", False)
###
#-- tex1mask = 1
# 0 = Org of [White] and [Red] are equal
# 1 = Org of [White] gets [Specularity] overlay
#-- tex1mask = 0 :: disables nip_specular
nip_specular = data.get("spec", 0.5)
nip_specular = max(nip_specular, 0) ## Min allowed value of [blend_modes]
nip_specular = min(nip_specular, 1) ## Max allowed value of [blend_modes]
###
# 0     = Full RGB-Color
# value = Red, (1 - value)*Green+(value * Red), (1 - value)*Blue+(value * Red)
# 1     = (Red, Red, Red) to be used as Alpha onto the BW version
tex1mask     = 1
#-------------
args = sys.argv[1:]
if details: print((f"\n=== Running overtex1(Body) Script with arguments:" + "\n-- %s" * len(args)) % tuple(args))
else: print(f"\n=== Running overtex1(Body) Script")
if legacy: print(f": Running in legacy mode")

if (nipsize < 0.01): print (f"[Warning]: Nipsize is very small or negative({nipsize}), may cause weird effects")

### Apply Transparency of 30% ( = 64 of 255)
alpha   = 64 / 255    ## For mask
beta    = 1.0 - alpha ## For main
show    = False       ## Do cv2.imshow

opt = imglib.makeOptions(locals())

### Read in pics
raw_image = imglib.TryLoadImage(imgMain, "MainTex")
mask      = imglib.TryLoadImage(imgMask, "Overtex")
#DisplayWithAspectRatio(opt, 'Org', raw_image, 512+256)
dim = raw_image.shape
yPad = 1; xPad = 1
if dim[0] != 2048: yPad = dim[0] / 2048
if dim[1] != 2048: xPad = dim[1] / 2048

### Rescale [nipsize] since it has different min / max boundaries (test exp() curve ?)
nipMax = nipsize_def + 0.66
nipMin = nipsize_def - 0.50
nipRange = nipMax - nipMin
nipsize = (nipsize * nipRange) + nipMin

### These cords work for a standard size of 2048 x 2048
_scale = 16
#cX_L  = int((195 - (_scale/2)) * xPad); cX_R  = int((382 - (_scale/2)) * xPad); cY    = int((285 - (_scale/2)) * yPad)
size  = ((64 / nipsize_def) * nipsize) + _scale
#size  = (nipsize) + _scale##: Keep using nipsize_def since that size was looking fine, so we rescale towards that
sizeX = size * xPad
sizeY = size * yPad

## UV of center: 0.1107986  0.1547173  \\  0.2024432  0.1547173
iSize = raw_image.shape
mSize = mask.shape

if show:
	print(f"Params: ((64 / {nipsize_def}) * {nipsize}) + {_scale}")
	print(f"Dims: {dim} --> {xPad} x {yPad}, size={size} ({sizeX} x {sizeY})")

#print(f"{iSize} -- {mSize}")
#uvX_L = 0.1107986 * iSize[1]; uvY_L = 0.1547173 * iSize[0]
#uvX_R = 0.2024432 * iSize[1]; uvY_R = 0.1547173 * iSize[0]
##print(f"UV (raw): {uvX_L} x {uvY_L} \\ {uvX_R} x {uvY_R}")
#uvX_L = (mSize[1]/2) - uvX_L; uvY_L = (mSize[0]/2) - uvY_L
#uvX_R = (mSize[1]/2) - uvX_R; uvY_R = (mSize[0]/2) - uvY_R

uvX_L = (0.1107986 * iSize[1]) - (sizeX / 2)
uvX_R = (0.2024432 * iSize[1]) - (sizeX / 2)
uvY_L = (0.1547173 * iSize[0]) - (sizeY / 2)
uvY_R = (0.1547173 * iSize[0]) - (sizeY / 2)
cX_L = abs(int(uvX_L))
cX_R = abs(int(uvX_R))
cY   = abs(int(uvY_L))

#print(f"UV: {uvX_L} x {uvY_L} \\ {uvX_R} x {uvY_R}")

## Pull out the alpha for later
if raw_image.shape[2] >= 4:
	imgAlpha = raw_image[:,:,3]
	image = raw_image[:,:,:3]
else:
	imgAlpha = np.zeros(raw_image.shape[:2], dtype='uint8') * 255
	image = raw_image
##
image = cv2.merge([image[:,:,0], image[:,:,1], image[:,:,2], imgAlpha])

#DisplayWithAspectRatio(opt, 'Mask only', mask, 256)

## Resize Mask to target size ---> x__resize_mask
maskRes = imglib.resize(mask, [sizeY, sizeX], inter=cv2.INTER_AREA)

## Make sure Color is not float anymore
overcolorInt = imglib.normalize_color(overcolor)

##------------ Main work
def conv(img): return img.astype(float)
def convI(img): return img.astype("uint8")
def modeTest(src, dst, name): return imglib.testOutModes(opt, src, dst, 256, name, True, _alpha=1)

#################################### Cut out segment (because org file is too big)
def cutHelper(_image, _area, insert=None):
	cY, cX = (_area[0],_area[1])
	pad = size % 2
	_aY = [int(cY), int((cY + pad + sizeY))]
	_aX = [int(cX), int((cX + pad + sizeX))]
	if insert is None:
		return _image[_aY[0]:_aY[1], _aX[0]:_aX[1], :]
	else:
		_image[_aY[0]:_aY[1], _aX[0]:_aX[1], :] = insert
		return _image

img_segR  = cutHelper(image, [cY, cX_R], None)
DisplayWithAspectRatio(opt, "ImgSegR", img_segR, 256)
if show:
	print(f"Sizes: {[cY, cX_R]} --> {img_segR.shape}")
####################################

### Do DisplayWithAspectRatio:
# on original color   [red] [white] [dar]
# on 50%              [red] [white] [dar]
# on natural Color    [red] [white] [dar]
# on 50% Specularity  [red] [white] [dar]
# on 100% Specularity [red] [white] [dar]

####################################
## Convert to float
image_f   = conv(img_segR)
imgBase_f = conv(maskRes)

## Handle one-off errors
if abs(image_f.shape[1] - imgBase_f.shape[1]) == 1 or abs(image_f.shape[1] - imgBase_f.shape[1]) == 1:
	imgBase_f = imglib.resize(imgBase_f, image_f.shape[:2], inter=cv2.INTER_AREA)
	maskRes   = imglib.resize(maskRes,   img_segR.shape[:2], inter=cv2.INTER_AREA)

DisplayWithAspectRatio_f(opt, 'Source (float,cut)', image_f, 256) ## Skin
DisplayWithAspectRatio_f(opt, 'Target (float)',   imgBase_f, 256) ## Texture
if show:
	print(f"> Source: {image_f.shape} vs. {imgBase_f.shape}")

imglib.testOutModes(opt, image_f, imgBase_f, 256, "Both Float", True, _alpha=1)

### Get color and apply self
# tex1mask: Affects alpha of [col_seg] by tex1mask%
# nip:      Affects size of [col_seg] by a small margin

####################################
## Split into separate channels

def extractChannel(src, chIdx):# Uses [maskRes, cv2, convI]
    maskCh = src[:,:,chIdx]
    
    ### Stretch to same shape as imgMain
    if (maskCh.shape[:2] != maskRes.shape[:2]):
        maskCh = cv2.resize(maskCh, (maskRes.shape[1], maskRes.shape[0]), interpolation=cv2.INTER_AREA)
    ### Widen into 3-Channel img_seg again
    maskChX = cv2.merge([maskCh, maskCh, maskCh, convI(maskRes)[:,:,3]])
    DisplayWithAspectRatio(opt, 'Channel '+str(chIdx), maskChX, 256) 

    return maskChX
#-----
cv2.destroyAllWindows()

maskB = extractChannel(mask, 0) ## Pink   == Color 3
maskG = extractChannel(mask, 1) ## Yellow == Color 2
maskR = extractChannel(mask, 2) ## Red    == Color 1

####################################
## Create a Color Image for reference

def getColorImg(_mask, _colArr):
	## Create an image of this color
	colImg0 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[0]
	colImg1 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[1]
	colImg2 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[2]
	return cv2.merge([colImg2, colImg1, colImg0, _mask[:,:,3]])
colImg = getColorImg(mask, overcolorInt)
DisplayWithAspectRatio(opt, "colImg", colImg, 256)

#####################
## img_segR \\ image_f ## maskRes \\ imgBase_f
#-- COLOR_BGR2HSV, COLOR_RGB2HSV, COLOR_HSV2BGR
col_hsv = imglib.arrCol(overcolorInt, cv2.COLOR_RGB2HSV)
img_hsv = cv2.cvtColor(maskRes, cv2.COLOR_BGR2HSV)
## Apply mix of color vs. tex1mask in percent
img_hsv[:,:,0] = col_hsv[0]
img_hsv[:,:,1] = col_hsv[1]
img_tex = cv2.cvtColor(img_hsv, cv2.COLOR_HSV2BGR)
img_tex = np.dstack([img_tex[:,:,:3], maskRes[:,:,3]])

def add_maskB(_img_seg):
	modeTest(_img_seg, img_tex, "maskB using HSV[0]")
	_image = imglib.blend_segmented(blend_modes.normal, conv(_img_seg), conv(img_tex), 1)
	DisplayWithAspectRatio(opt, "Great", _image, 256)
	return _image
if legacy: img_seg = add_maskB(img_segR)

####
## Apply Specularity
##-- Black: normal, mul, darken, hard_light
##-- Screen looks the closest to without -- Try out with just appling BW 
def add_maskG(_img_seg):
	modeTest(_img_seg, maskG, "normal + maskG")
	#_image = imglib.blend_segmented(blend_modes.screen, _img_seg, maskG, nip_specular)
	_image = imglib.blend_segmented(blend_modes.overlay, _img_seg, maskG, nip_specular)
	DisplayWithAspectRatio(opt, "Great 2", _image, 256)
	return _image
if legacy: img_seg = add_maskG(img_seg)

 ## Looks good, but needs more testing if actually required.
def add_maskR(_img_seg):## -- Adds back a bit of contrast
	modeTest(_img_seg, maskR, "normal + maskR")
	_image = imglib.blend_segmented(blend_modes.multiply, _img_seg, maskR, 1)
	DisplayWithAspectRatio(opt, "Great 3", _image, 256)
	return _image
if legacy: img_seg = add_maskR(img_seg)

# DisplayWithAspectRatio(opt, 'Final Seg[CV2]', conv(img_seg), 256)
def modeTest2(src, dst, name): pass
modeTest = modeTest2

#### Paste back
if not legacy:
	####--- Hard reset since we have a white one now
	# testOutModes_wrap
	img_seg = imglib.blend_segmented(blend_modes.multiply, conv(img_segR), conv(maskRes), 1)
	#--- multiply and SoftLight

image = cutHelper(image, [cY, cX_R], img_seg)

###################### Other side
img_segL  = cutHelper(image, [cY, cX_L], None)

if legacy:
	img_seg = add_maskB(img_segL)
	img_seg = add_maskG(img_seg)
	img_seg = add_maskR(img_seg)
else:
	img_seg = imglib.blend_segmented(blend_modes.multiply, conv(img_segL), conv(maskRes), 1)

image = cutHelper(image, [cY, cX_L], img_seg)
######################
#print(f'Parts: {cY} {cX_L} {cX_R} \\ {size}  {sizeX}  {sizeY}')
#print(f'Size:: {cY-size*2}:{cY+size*2}, {cX_L-size}:{cX_R+size}')
#print(f'SizeX: {cY-sizeY*2}:{cY+sizeY*2}, {cX_L-sizeX}:{cX_R+sizeX}')
#print([int(max(0,cY-sizeY*2)),int(cY+sizeY*2), int(max(0,cX_L-sizeX)),int(cX_R+sizeX)])

DisplayWithAspectRatio(opt, 'Final', image[int(max(0,cY-sizeY*2)):int(cY+sizeY*2), int(max(0,cX_L-sizeX)):int(cX_R+sizeX), :], None, 512+256)
if show: k = cv2.waitKey(0) & 0xFF
cv2.destroyAllWindows()

### Write out final image
outName = imgMain[:-4] + "_pyOT1.png"
imglib.TryWriteImage(outName, image)
print("Wrote output image at\n" + outName)
