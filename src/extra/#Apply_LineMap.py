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

#-------------
imgMain = sys.argv[1] ## MainTex.png
imgMask = sys.argv[2] ## LineMask.png
#-------------
data    = {}
if (len(sys.argv) > 3): data = json.loads(sys.argv[3])
verbose  = data.get("showinfo", False)
mainSize = data.get("mainSize", True)
mode     = data.get("mode", "overlay")
#-------------
# value  = (Checkbox) of "body".tex__Line.Green
linetexon    = data.get("linetexon", 1)
#-------------
args = sys.argv[1:]
if verbose: print(("\n=== Running LineMask Script with arguments:" + "\n-- %s" * len(args)) % tuple(args))
else: print("\n === Running LineMask Script ")


### Apply Transparency of 30% ( = 64 of 255)
alpha   = 64 / 255    ## For mask
beta    = 1.0 - alpha ## For main
show    = False       ## Do cv2.imshow
opt = imglib.makeOptions(locals())

### Read in pics
raw_image = cv2.imread(imgMain, cv2.IMREAD_UNCHANGED)
mask = cv2.imread(imgMask)
DisplayWithAspectRatio(opt, 'Org', raw_image, 256)

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
    maskChX = imglib.extendChannel(maskCh, maskCh)
    DisplayWithAspectRatio(opt, 'Channel '+str(chIdx)+ ': ', maskChX, 256)

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

colArr = image[0,0,:]
#colImg = imglib.getColorMask(opt, maskB[:,:,3], colArr, useKKOrder=False)
#colImg[:,:,3] = maskB[:,:,3]
#DisplayWithAspectRatio(opt, 'ColImg+Alpha', colImg, 256)
colImg = imglib.getColorImg(opt, maskB, colArr)

#imglib.testOutModes_wrap(image, colImg)
image = imglib.blend_segmented("multiply", image, colImg, alpha)#.astype("uint8")


#####
# [Adds Grey]: Not, Mul, GExtract, Darken \\ (Light): HardLight, GMerge
# [Decent]: Ovl > Lighten, SoftLight, Screen, Div
#imglib.testOutModes_wrap(image, maskB)
#
#image = imglib.blend_segmented("overlay", image, maskB, alpha)#.astype("uint8")

#imglib.testOutModes_wrap(image, maskG)
#image = imglib.blend_segmented("overlay", image, maskG, linetexon).astype("uint8")


##if (flag): ## Add Top -> Bottom \\ Unknown why it should have been controlable
#mixMask = cv2.addWeighted(maskG, 0.5, maskB, 0.5, 0)
#DisplayWithAspectRatio(opt, 'MixMask', mixMask, 256)
#imglib.testOutModes_wrap(image, mixMask)

#image = imglib.blend_segmented(mode, image, mixMask, alpha).astype("uint8")
#image = cv2.addWeighted(image, beta, mixMask, alpha, 0)
#DisplayWithAspectRatio(opt, 'With MixMask', image, 256)

### Remerge Alpha
#image = cv2.merge([image[:,:,0], image[:,:,1], image[:,:,2], imgAlpha])

DisplayWithAspectRatio(opt, 'Final', image.astype("uint8"), 256)
if show: k = cv2.waitKey(0) & 0xFF

### Write out final image
outName = imgMain[:-4] + "_pyLin.png"
cv2.imwrite(outName, image)
print("Wrote output image at\n" + outName)
