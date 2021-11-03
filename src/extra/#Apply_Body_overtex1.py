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
print(("\n=== Running overtex1(Body) Script with arguments:" + "\n-- %s" * len(args)) % tuple(args))
#-------------
imgMain   = sys.argv[1] ## MainTex.png
imgMask   = sys.argv[2] ## overtex.png
data      = json.loads(sys.argv[3])
#-------------
nip          = data.get("nip", 1.0)        ## Scales texture a bit
nipsize      = data.get("size", 0.6677417) ## Increases Factor for nip (== Areola Size)
###
overcolor    = data["color"]
###
#-- tex1mask = 1
# 0 = Org of [White] and [Red] are equal
# 1 = Org of [White] gets [Specularity] overlay
#-- tex1mask = 0 :: disables nip_specular
nip_specular = data.get("spec", 0.5)
nip_specular = min(nip_specular, 1) ## Max allowed value of [blend_modes]
###
# 0     = Full RGB-Color
# value = Red, (1 - value)*Green+(value * Red), (1 - value)*Blue+(value * Red)
# 1     = (Red, Red, Red) to be used as Alpha onto the BW version
tex1mask     = 1
#-------------

### Apply Transparency of 30% ( = 64 of 255)
alpha   = 64 / 255    ## For mask
beta    = 1.0 - alpha ## For main
show    = False       ## Do cv2.imshow

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

## Resize Mask to target size ---> x__resize_mask
maskRes = imglib.resize(mask, [size, size])

## Make sure Color is not float anymore
overcolorInt = imglib.normalize_color(overcolor)

##------------ Main work
def conv(img): return img.astype(float)
def convI(img): return img.astype("uint8")

#### Workaround since unable to figure out consistent way that works for both
sumR = maskRes[:,:,0].sum().astype('int64')
sumG = maskRes[:,:,1].sum().astype('int64')
sumB = maskRes[:,:,2].sum().astype('int64')

is_bitmask = (abs(sumR - sumG) < 500) and (abs(sumR - sumB) < 500)

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

DisplayWithAspectRatio_f(opt, 'Source (float,cut)', image_f, 256) ## Skin
DisplayWithAspectRatio_f(opt, 'Target (float)',   imgBase_f, 256) ## Texture

imglib.testOutModes(opt, image_f, imgBase_f, 256, "Both Float", True, _alpha=1)

### Get color and apply self
# tex1mask: Affects alpha of [col_seg] by tex1mask%
# nip:      Affects size of [col_seg] by a small margin
col_seg = imglib.getColorMask(opt, convI(imgBase_f), overcolorInt, "")
DisplayWithAspectRatio_f(opt, 'ColorMask', conv(col_seg), 256)
col_seg2 = imglib.colorizeBitmask(opt, convI(imgBase_f), overcolorInt, "")
DisplayWithAspectRatio_f(opt, 'ColorMask (BM)', conv(col_seg2), 256)

if not is_bitmask: col_seg = col_seg2

col_seg = conv(col_seg)

_alpha = 1#192/255

####
##-- Only normal keeps BG, all else use the Black BG of the mask
#imglib.testOutModes(opt, conv(col_seg), image_f, 256, "Color + Img", True, _alpha=_alpha)

mode_1 = blend_modes.normal if is_bitmask else blend_modes.multiply
img_seg = mode_1(image_f, conv(col_seg), _alpha)
DisplayWithAspectRatio_f(opt, 'ImgSeg', img_seg, 256)## >> Useless

# tex1mask: Affects bleeding of [col_seg] non-R channels (0 = keep 100%, 1 = R,R,R)
test = imglib.extendChannel(imgBase_f[:,:,0], imgBase_f[:,:,3])
test2 = imglib.extendChannel(imgBase_f[:,:,1], imgBase_f[:,:,3])

imglib.testOutModes(opt, conv(img_seg), test, 256, "ImgSeg + Mask", True, _alpha=1)
##>> Looks ok again

mode_2 = blend_modes.multiply if is_bitmask else blend_modes.screen

img_seg = mode_2(conv(img_seg), test, 1)
DisplayWithAspectRatio_f(opt, 'ImgSeg after Test', img_seg, 256)## >> Useless
img_seg = mode_2(conv(img_seg), test2, nip_specular)
DisplayWithAspectRatio_f(opt, 'ImgSeg after Test2', img_seg, 256)## >> Useless
##---

DisplayWithAspectRatio(opt, 'Final Seg[CV2]', conv(img_seg), 256)

#### Paste back
image = cutHelper(image, [cY, cX_R], conv(img_seg))

###################### Other side
img_segL  = cutHelper(image, [cY, cX_L], None)
image_f   = conv(img_segL)

img_seg = mode_1(image_f, conv(col_seg), _alpha)
img_seg = mode_2(conv(img_seg), test, 1)
img_seg = mode_2(conv(img_seg), test2, nip_specular)

#img_seg = blend_modes.multiply(image_f, conv(col_seg), _alpha)
##img_seg = blend_modes.multiply(conv(img_seg), test, 1)
#if do_spec: img_seg = blend_modes.multiply(conv(img_seg), test2, nip_specular)

image = cutHelper(image, [cY, cX_L], img_seg)
######################

DisplayWithAspectRatio(opt, 'Final', image[cY-size*2:cY+size*2, cX_L-size:cX_R+size, :], None, 512+256)
if show: k = cv2.waitKey(0) & 0xFF

### Write out final image
outName = imgMain[:-4] + "_pyOT1.png"
cv2.imwrite(outName, image)
print("Wrote output image at\n" + outName)
