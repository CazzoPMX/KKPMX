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

args = sys.argv[1:]
print(("\n=== Running Body overtex1 Script with arguments:" + "\n-- %s" * len(args)) % tuple(args))
#-------------
imgMain   = sys.argv[1] ## MainTex.png
imgMask   = sys.argv[2] ## overtex.png
overcolor = json.loads(sys.argv[3])
#-------------
nip          = 1.0        ## Scales texture a bit
nipsize      = 0.6677417  ## Scales texture a lot (Areola Size)
###
#-- tex1mask = 1
# 0 = Org of [White] and [Red] are equal
# 1 = Org of [White] gets [Specularity] overlay
#-- tex1mask = 0 :: disables nip_specular
nip_specular = 0.5
###
# 0     = Full RGB-Color
# value = Red, (1 - value)*Green+(value * Red), (1 - value)*Blue+(value * Red)
# 1     = (Red, Red, Red) to be used as Alpha
tex1mask     = 1
#-------------


### Apply Transparency of 30% ( = 64 of 255)
alpha   = 64 / 255    ## For mask
beta    = 1.0 - alpha ## For main
show    = False       ## Do cv2.imshow
scale   = 1

cX_L  = 195
cX_R  = 382
cY    = 285
size  = 64

opt = imglib.makeOptions(locals())

### Read in pics
raw_image = cv2.imread(imgMain, cv2.IMREAD_UNCHANGED)
mask      = cv2.imread(imgMask, cv2.IMREAD_UNCHANGED)
#DisplayWithAspectRatio(opt, 'Org', raw_image, 512+256)

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

def extractChannel(src, chIdx):
    ### Extract channels and not invert them
    #maskCh = 255 - src[:,:,chIdx]
    maskCh = src[:,:,chIdx]

    ### Stretch to same shape as imgMain
    if (maskCh.shape[:2] != [size, size]):
        target = [size, size]
        source = maskCh.shape
        width  = int(source[1] * (target[1] / source[1]))
        height = int(source[0] * (target[0] / source[0]))
        maskCh = cv2.resize(maskCh, (width, height), interpolation=cv2.INTER_NEAREST)
    
    ### Widen into 3-Channel image again
    maskChX = cv2.merge([maskCh, maskCh, maskCh])
    DisplayWithAspectRatio(opt, 'Channel '+str(chIdx)+ ': ', maskChX, 256)

    return maskChX
#-----
### Split channels to get DisplayWithAspectRatio
maskB = extractChannel(mask, 2) ## NormalMask.Y (?)
maskG = extractChannel(mask, 1) ## Specularity -- affected by [nip_specular]
maskR = extractChannel(mask, 0) ## MainTex ++ NormalMask.X
maskA = extractChannel(mask, 3) ## Alpha

### image, invert, target, dispSize
## (maskR, maskG, maskB, maskA) = imglib.splitChannels(mask, True, [64,64], 256)

## Resize Mask to target size ---> x__resize_mask
maskRes = imglib.resize(mask, [size, size])

## Convert [x__resize_mask] to Grayscale --> x__mask_BW
#maskRes = imglib.convert_to_BW(maskRes)

## Make sure Color is not float anymore
overcolorInt = imglib.normalize_color(overcolor)

##------------ Main work

def converter(img): return (img / scale).astype(float)


#################################### Cut out segment (because org file is too big)
def cutHelper(_image, _area, insert=None):
	cY, cX = (_area[0],_area[1])
	_aY = [int(cY), int(cY + size)]
	_aX = [int(cX), int(cX + size)]
	if insert is None:
		return _image[_aY[0]:_aY[1], _aX[0]:_aX[1], :]
	else:
		_image[_aY[0]:_aY[1], _aX[0]:_aX[1], :] = insert
		return _image

img_segR  = cutHelper(image, [cY, cX_R], None)
#DisplayWithAspectRatio(opt, 'Cut from Main', img_seg.astype("uint8"), 256)
####################################
## Convert to float
image_f   = converter(img_segR)
imgBase_f = converter(maskRes)

DisplayWithAspectRatio_f(opt, 'Source (float,cut)', image_f, 256)
DisplayWithAspectRatio_f(opt, 'Target (float)',   imgBase_f, 256)

imglib.testOutModes(opt, image_f, imgBase_f, 256, "Both Float", True, _alpha=1)

### Get color and apply self
# tex1mask: Affects alpha of [col_seg] by tex1mask%
# nip:      Affects size of [col_seg] by a small margin
col_seg = imglib.getColorMask(opt, (imgBase_f*scale).astype("uint8"), overcolorInt, "tag")

_alpha = 192/255
imglib.testOutModes(opt, image_f, converter(col_seg), 256, "Img + Color", True, _alpha=_alpha)
img_seg = blend_modes.normal(image_f, converter(col_seg), _alpha) * scale

# tex1mask: Affects bleeding of [col_seg] non-R channels (0 = keep 100%, 1 = R,R,R)
test = imglib.extendChannel(imgBase_f[:,:,0], imgBase_f[:,:,3])
test2 = imglib.extendChannel(imgBase_f[:,:,1], imgBase_f[:,:,3])

imglib.testOutModes(opt, converter(img_seg), test, 256, "ImgSeg + Mask", True, _alpha=1)
img_seg = blend_modes.overlay(converter(img_seg), test, 1) * scale
img_seg = blend_modes.overlay(converter(img_seg), test2, nip_specular) * scale

DisplayWithAspectRatio(opt, 'Final Seg[CV2]', img_seg, 256)

#### Paste back
image = cutHelper(image, [cY, cX_R], img_seg)

###################### Other side
img_segL  = cutHelper(image, [cY, cX_L], None)
image_f   = converter(img_segL)

img_seg = blend_modes.normal(image_f, converter(col_seg), _alpha) * scale
img_seg = blend_modes.overlay(converter(img_seg), test, 1) * scale
img_seg = blend_modes.overlay(converter(img_seg), test2, nip_specular) * scale

image = cutHelper(image, [cY, cX_L], img_seg)
######################

DisplayWithAspectRatio(opt, 'Final', image[cY-size*2:cY+size*2, cX_L-size:cX_R+size, :], None, 512+256)
if show: k = cv2.waitKey(0) & 0xFF

### Remerge Alpha
#image = cv2.merge([image[:,:,0], image[:,:,1], image[:,:,2], imgAlpha.astype(float)])

### Write out final image
outName = imgMain[:-4] + "_pyOT1.png"
cv2.imwrite(outName, image)
print("Wrote output image at\n" + outName)
