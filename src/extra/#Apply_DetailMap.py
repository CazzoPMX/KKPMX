import cv2
import numpy as np
import sys,json

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

argLen = len(sys.argv)
if (argLen < 2):
	print("Must have at least 2 arguments")
	exit()

#-------------
imgMain = sys.argv[1] ## MainTex.png
imgMask = sys.argv[2] ## DetailMask.png
#-------------
data = {}
if (argLen > 3): data = json.loads(sys.argv[3])
mode            = data.get("mode", "overlay")
details         = data.get("moreinfo", True)
mainSize        = data.get("is_main", False)
is_body         = data.get("is_body", False)
#-------------
_mask = None;imgAlpha = ""
if (argLen > 4): imgAlpha = sys.argv[4]
has_detail = len(imgMask) > 0
has_alpha  = len(imgAlpha) > 0
#-------------
name = "DetailMask"
if has_detail and has_alpha: name = "Detail/Alpha-Mask"
elif not has_detail and has_alpha: name = "Alpha-Mask"

args = sys.argv[1:]
if details: print((f"\n=== Running {name} Script with arguments:" + "\n-- %s" * len(args)) % tuple(args))
else: print(f"\n=== Running {name} Script")

### Apply Transparency of 30% ( = 64 of 255)
alpha   = 64 / 255    ## For mask
show    = False       ## Do cv2.imshow
opt = imglib.makeOptions(locals())

### Read in pics
raw_image = cv2.imread(imgMain, cv2.IMREAD_UNCHANGED)
if has_detail: mask = cv2.imread(imgMask)
if has_alpha: _mask = cv2.imread(imgAlpha)

#if show: cv2.imshow('Org', raw_image)

## Pull out the alpha for later

if raw_image.shape[2] >= 4: # @todo_add:: extract_alpha(raw_image) --> (image, rawAlpha, has_alpha)
	rawAlpha = raw_image[:,:,3]
	image = raw_image[:,:,:3]
else:
	rawAlpha = np.ones(raw_image.shape[:2], dtype='uint8') * 255
	image = raw_image

def apply_alpha_mask__(image, _mask):
	bitmask = np.ones(_mask.shape[:2], dtype="uint8") * 255
	bitmask[:,:] = (_mask[:,:,0] != 0)
	bitmask = cv2.merge([bitmask*255, bitmask*255, bitmask*255])
	tmp = np.ones(image.shape, dtype="uint8") * 255
	inverted = imglib.blend_segmented(blend_modes.difference, tmp, bitmask, 1)
	image = imglib.blend_segmented(blend_modes.multiply, image, inverted, 1)
	return image

def apply_alpha_mask(image, _mask, rawAlpha):
	import blend_modes
	DisplayWithAspectRatio(opt, 'Alpha-Mask', _mask, 256)
	##-- Smooth out black colors into binary 0
	## Can have green or yellow parts as well, so convert to BW as well.
	imgBW = cv2.cvtColor(imglib.smooth_black(_mask), cv2.COLOR_BGR2GRAY)
	bitmask = np.ones(imgBW.shape[:2], dtype="uint8") * 255
	bitmask[:,:] = (imgBW != 0)
	bitmask = cv2.merge([bitmask*255, bitmask*255, bitmask*255])
	DisplayWithAspectRatio(opt, 'Bitmask', bitmask, 256)
	
	bitmask = imglib.resize(bitmask, image)
	
	image = imglib.blend_segmented(blend_modes.multiply, image, bitmask, 1)
	
	DisplayWithAspectRatio(opt, 'Alpha.d', image, 256)
	return (bitmask[:,:,0], image)

if has_alpha and not has_detail: ## << Only apply Alpha-Mask
	(rawAlpha, image) = apply_alpha_mask(image, _mask, rawAlpha)
	#image = cv2.merge([image[:,:,0], image[:,:,1], image[:,:,2], rawAlpha])
	image = np.dstack([image[:,:,:3], rawAlpha])

	DisplayWithAspectRatio(opt, 'Final', image, 512)
	if show: k = cv2.waitKey(0) & 0xFF

	### Write out final image
	outName = imgMain[:-4] + "_pyDet.png"
	cv2.imwrite(outName, image)
	print("Wrote output image at\n" + outName)
	exit()
	pass#--------------------


#-----------------------
def extractChannel_X(src, chIdx):
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
def extractChannel_col(src, chIdx):# << ColorMask version
    ### Extract channels and invert them
    maskCh = 255 - src[:,:,chIdx]
    ### ... or not. Tried at end again, and yes, no invert
    maskCh = src[:,:,chIdx]
    
    ### Stretch to same shape as imgMain
    if (maskCh.shape[:2] != image.shape[:2]) and mainSize:
        maskCh = cv2.resize(maskCh, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_NEAREST)
    ### Widen into 3-Channel image again
    maskChX = cv2.merge([maskCh, maskCh, maskCh])
    #DisplayWithAspectRatio(opt, 'Channel '+str(chIdx)+ ': ', maskChX) 

    return maskChX
#-----
if False:## Is Inverted -- If any, only "is_body" anyway....
	fix_value = 0
	extractChannel = extractChannel_col
else: ## is not -- everything is adjusted to this
	extractChannel = extractChannel_X
	fix_value = 255
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
	rawAlpha = cv2.resize(rawAlpha, (width, height), interpolation=cv2.INTER_NEAREST)

### Make colors stronger before being toned down again
#hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
#hsv[:,:,1] = hsv[:,:,1] + 10
#image = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
#if show: cv2.imshow('Stronger', image)

#####
# [Adds Grey]: Not, Mul, GExtract, Darken \\ (Light): HardLight, GMerge
# [Decent]: Ovl > Lighten, SoftLight, Screen, Div
DisplayWithAspectRatio(opt, 'maskB', maskB, 512)

if is_body:
	#### Remove an ANNOYING alpha:0 heart shaped crest on chest
	## Coords: x:256,y:220 --> 128,124 
	imgFix = np.ones((128,128,3), dtype='uint8') * fix_value
	maskB[220:220+128, 256:256+128, :] = imgFix
	DisplayWithAspectRatio(opt, 'Fixed maskB', maskB, 512)

imageB = imglib.blend_segmented(mode, image, maskB, alpha).astype("uint8")
DisplayWithAspectRatio(opt, 'With maskB', imageB, 512)

image = imglib.blend_segmented(mode, imageB, maskG, alpha).astype("uint8")
DisplayWithAspectRatio(opt, 'With maskB+maskG', image, 512)

### Apply Alpha-Mask
if has_alpha: (rawAlpha, image) = apply_alpha_mask(image, _mask, rawAlpha)

### Remerge Alpha
try:
	#image = cv2.merge([image[:,:,0], image[:,:,1], image[:,:,2], rawAlpha.astype("float")])
	image = np.dstack([image[:,:,:3], rawAlpha])
except Exception as ex:
	print(ex)
	#image = imglib.resize(rawAlpha, image)
	#image = cv2.merge([image[:,:,0], image[:,:,1], image[:,:,2], rawAlpha])
	print(f"> Failed to re-apply alpha: {image.shape} vs. {rawAlpha.shape}")

DisplayWithAspectRatio(opt, 'Final', image, 512)
if show: k = cv2.waitKey(0) & 0xFF

### Write out final image
outName = imgMain[:-4] + "_pyDet.png"
cv2.imwrite(outName, image)
print("Wrote output image at\n" + outName)