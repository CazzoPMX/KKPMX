import cv2
import numpy as np
import sys

try:
	from kkpmx_image_lib import DisplayWithAspectRatio, DisplayWithAspectRatio_f
	import kkpmx_image_lib as imglib
except ImportError as eee:
	from . import kkpmx_image_lib as imglib
	DisplayWithAspectRatio = imglib.DisplayWithAspectRatio
	DisplayWithAspectRatio_f = imglib.DisplayWithAspectRatio_f


todos="""
-- Make results better (currently just the full image is toned down)
-- Find a use for the third layer (probably as *.fx in combination with NormalMask)
"""

#-------------
imgMain = sys.argv[1] ## MainTex.png
imgMask = sys.argv[2] ## DetailMask.png
details = False
mainSize = True
mode = "overlay"
is_body = False
if len(sys.argv) > 3: details = sys.argv[3] == 'True'
if len(sys.argv) > 4: mainSize = bool(sys.argv[4])
if len(sys.argv) > 5: mode = sys.argv[5]
if len(sys.argv) > 6: is_body = sys.argv[6] == 'True'
#-------------
#data = {}
#if (argLen > 3): data = json.loads(sys.argv[3])
#mode            = data.get("mode", "Overlay")
#details         = data.get("moreinfo", False)
#mainSize        = data.get("hair", True)
#is_body         = data.get("is_body", False)
#-------------
args = sys.argv[1:]
if details: print(("\n=== Running DetailMask Script with arguments:" + "\n-- %s" * len(args)) % tuple(args))
else: print("\n=== Running DetailMask Script")

### Apply Transparency of 30% ( = 64 of 255)
alpha   = 64 / 255    ## For mask
beta    = 1.0 - alpha ## For main
show    = False       ## Do cv2.imshow
opt = imglib.makeOptions(locals())

### Read in pics
raw_image = cv2.imread(imgMain, cv2.IMREAD_UNCHANGED)
mask = cv2.imread(imgMask)
#if show: cv2.imshow('Org', raw_image)

## Pull out the alpha for later
if raw_image.shape[2] >= 4: # @todo_add:: extract_alpha(raw_image) --> (image, imgAlpha, has_alpha)
	imgAlpha = raw_image[:,:,3]
	image = raw_image[:,:,:3]
else:
	imgAlpha = np.ones(raw_image.shape[:2], dtype='uint8') * 255
	image = raw_image

def extractChannel(src, chIdx):
    ### Extract channels and invert them
    maskCh = 255 - src[:,:,chIdx]
    
    ### Stretch to same shape as imgMain
    if (maskCh.shape[:2] != image.shape[:2]) and mainSize:
        target = image.shape
        source = maskCh.shape
        width  = int(source[1] * (target[1] / source[1]))
        height = int(source[0] * (target[0] / source[0]))
        maskCh = cv2.resize(maskCh, (width, height), interpolation=cv2.INTER_NEAREST)
    ### Widen into 3-Channel image again
    maskChX = cv2.merge([maskCh, maskCh, maskCh])
    return maskChX
#-----
cv2.destroyAllWindows()
maskB = extractChannel(mask, 0) ## NormalMask.Y (?)
maskG = extractChannel(mask, 1) ## Smoothness
#maskR = extractChannel(mask, 2) ## Specularity

if (mask.shape[:2] != image.shape[:2]) and (not mainSize): # @todo_add:: resize_image(img, target, source)
	target = mask.shape
	source = image.shape
	width  = int(source[1] * (target[1] / source[1]))
	height = int(source[0] * (target[0] / source[0]))
	image = cv2.resize(image, (width, height), interpolation=cv2.INTER_NEAREST)

### Make colors stronger before being toned down again
#hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
#hsv[:,:,1] = hsv[:,:,1] + 10
#image = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
#if show: cv2.imshow('Stronger', image)

#####
# [Adds Grey]: Not, Mul, GExtract, Darken \\ (Light): HardLight, GMerge
# [Decent]: Ovl > Lighten, SoftLight, Screen, Div
DisplayWithAspectRatio(opt, 'maskB', maskB, 512)
#imglib.testOutModes_wrap(image, maskB)
#cv2.imwrite(imgMain[:-4] + "_pyDet_maskB.png", maskB)

#### Color Tests
if False:
	colImg = imglib.getColorImg(opt, maskB, image[0,0,:])
	maskBCol = imglib.blend_segmented("overlay", colImg, maskB, alpha).astype("uint8")
	#DisplayWithAspectRatio(opt, 'colImg', maskBCol, 512)
	#imglib.testOutModes_wrap(image, maskBCol)
	cv2.imwrite(imgMain[:-4] + "_pyDet_maskBCol.png", maskBCol)


if is_body:
	#### Remove an ANNOYING alpha:0 heart shaped crest on chest
	## Coords: x:256,y:220 --> 128,124 
	imgFix = np.ones((128,128,3), dtype='uint8') * 240
	maskB[220:220+128, 256:256+128, :] = imgFix
	DisplayWithAspectRatio(opt, 'Fixed maskB', maskB, 512)

imageB = imglib.blend_segmented(mode, image, maskB, alpha).astype("uint8")
DisplayWithAspectRatio(opt, 'With maskB', imageB, 512)

#imageG = imglib.blend_segmented(mode, image, maskG, alpha).astype("uint8")
#DisplayWithAspectRatio(opt, 'With maskG', imageG, 512)

#image = imglib.blend_segmented(mode, imageG, maskB, alpha).astype("uint8")
#DisplayWithAspectRatio(opt, 'With maskG+maskB', image, 512)
#cv2.imwrite(imgMain[:-4] + "_pyDet_G+B.png", image)

image = imglib.blend_segmented(mode, imageB, maskG, alpha).astype("uint8")
DisplayWithAspectRatio(opt, 'With maskB+maskG', image, 512)
### Remerge Alpha
image = cv2.merge([image[:,:,0], image[:,:,1], image[:,:,2], imgAlpha])

DisplayWithAspectRatio(opt, 'Final', image, 512)
if show: k = cv2.waitKey(0) & 0xFF

### Write out final image
outName = imgMain[:-4] + "_pyDet.png"
cv2.imwrite(outName, image)
print("Wrote output image at\n" + outName)
