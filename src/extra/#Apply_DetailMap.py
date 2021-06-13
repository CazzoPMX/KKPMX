import cv2
import numpy as np
import sys

try:
	import kkpmx_image_lib as imglib
except ImportError as eee:
	from . import kkpmx_image_lib as imglib


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
if len(sys.argv) > 3: details = bool(sys.argv[4])
if len(sys.argv) > 4: mainSize = bool(sys.argv[4])
if len(sys.argv) > 5: mode = sys.argv[5]
#-------------
args = sys.argv[1:]
if details: print(("\n=== Running DetailMask Script with arguments:" + "\n-- %s" * len(args)) % tuple(args))


### Apply Transparency of 30% ( = 64 of 255)
alpha   = 64 / 255    ## For mask
beta    = 1.0 - alpha ## For main
show    = False       ## Do cv2.imshow
opt = imglib.makeOptions(locals())

### Read in pics
raw_image = cv2.imread(imgMain, cv2.IMREAD_UNCHANGED)
mask = cv2.imread(imgMask)
if show: cv2.imshow('Org', raw_image)

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
        #print("{} * ({} / {} = {}) == {}".format(source[1], target[1], source[1], target[1] / source[1], width))
        #print("{} * ({} / {} = {}) == {}".format(source[0], target[0], source[0], target[0] / source[0], height))
        maskCh = cv2.resize(maskCh, (width, height), interpolation=cv2.INTER_NEAREST)
    ### Widen into 3-Channel image again
    maskChX = cv2.merge([maskCh, maskCh, maskCh])
    #if show: cv2.imshow('Channel '+str(chIdx)+ ': ', maskChX) 

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
	#print("{} * ({} / {} = {}) == {}".format(source[1], target[1], source[1], target[1] / source[1], width))
	#print("{} * ({} / {} = {}) == {}".format(source[0], target[0], source[0], target[0] / source[0], height))
	image = cv2.resize(image, (width, height), interpolation=cv2.INTER_NEAREST)

### Make colors stronger before being toned down again
#hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
#hsv[:,:,1] = hsv[:,:,1] + 10
#image = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
#if show: cv2.imshow('Stronger', image)

desc = """
If we are strict, then mainTex is merged last (bottom most layer)
Which means, merge the masks first
Otherwise, the masks look like in paint.Net (when [mainTex] is off)
"""
##if (flag): ## Add Top -> Bottom \\ Unknown why it should have been controlable
mixMask = cv2.addWeighted(maskG, 0.5, maskB, 0.5, 0)
if show: cv2.imshow('MixMask', mixMask)
#imglib.testOutModes_wrap(image, mixMask)

image = imglib.blend_segmented(mode, image, mixMask, alpha).astype("uint8")
#image = cv2.addWeighted(image, beta, mixMask, alpha, 0)
if show: cv2.imshow('With MixMask', image)

### Remerge Alpha
image = cv2.merge([image[:,:,0], image[:,:,1], image[:,:,2], imgAlpha])

if show: cv2.imshow('Final', image.astype("uint8"))
if show: k = cv2.waitKey(0) & 0xFF

### Write out final image
outName = imgMain[:-4] + "_pyDet.png"
cv2.imwrite(outName, image)
print("Wrote output image at\n" + outName)
