import cv2
import numpy as np
import sys
import json
import blend_modes

try:
	import kkpmx_image_lib as imglib
except ImportError as eee:
	from . import kkpmx_image_lib as imglib

todos="""
-- Support MainTex
-- Support colB_3Pink
"""

argLen = len(sys.argv)
if (argLen == 4 | argLen < 3):
	print("Must have 3 or 5 arguments")
	exit()

arguments_help = """
[1]: Path to MainTex   :: can be empty
[2]: Path to ColorMask :: IOError if not found
[3]: The first Color (R), used for red areas
[4]: The second Color (G), used for yellow areas
[5]: The third Color (B), used for pink areas
[6]: Color mode (actually always 'Additive')

3 4 5 are RGB or RGBA arrays mapped to 0...1
"""

### Read in arguments
imgMain = sys.argv[1] ## MainTex.png
imgMask = sys.argv[2] ## ColorMask.png
noMainTex = len(imgMain) == 0

printMsg = "\n=== Running ColorMask Script with:\n-- {}\n-- {}\n-- {}".format(imgMain, imgMask, sys.argv[3])
if argLen > 4: printMsg = printMsg + "\n-- {}\n-- {}".format(sys.argv[4], sys.argv[5])
if argLen > 6: printMsg = printMsg + "\n-- {}".format(sys.argv[6])
print(printMsg)

colorArr = []
#input --> int(float * 255) or RGB, single or arr.len=3
#if argLen == 3:
#	c = int(sys.argv[3])
#	colorArr = [c,c,c]
#else:
#	r = int(sys.argv[3])
#	g = int(sys.argv[4])
#	b = int(sys.argv[5])
#	colorArr = [r,g,b]
#colR,colG,colB = colorArr


colB_3Pink   = json.loads(sys.argv[5])
colG_1Yellow = json.loads(sys.argv[4])
colR_2Red    = json.loads(sys.argv[3])
mode         = "Overlay"
if (argLen > 6): mode = sys.argv[6]

#---------- Flags
### Apply Transparency of 30% ( = 64 of 255)
alpha     = 64 / 255    ## For mask
beta      = 1.0 - alpha ## For main
show      = False       ## Do cv2.imshow
noMainTex = len(imgMain) == 0

def isUseful(arr):
	if arr is None: return False
	if len(arr) < 3: return False
	return all([a == 0 for a in arr]) == False

flagRed   = isUseful(colR_2Red)
flagGreen = isUseful(colG_1Yellow)
flagBlue  = isUseful(colB_3Pink)

### Read in pics
raw_image = None
mask = cv2.imread(imgMask)
if mask is None:
	raise IOError("File '{}' does not exist.".format(imgMask))

if (noMainTex): ## Color may not always have a mainTex
	image = np.ones(mask.shape[:2], dtype='uint8') * 255
	raw_image = cv2.merge([image, image, image])
	image = None
else:
	raw_image = cv2.imread(imgMain, cv2.IMREAD_UNCHANGED)
	if show: cv2.imshow('Org', raw_image)


## Pull out the alpha for later
has_alpha = raw_image.shape[2] >= 4
if has_alpha:
	imgAlpha = raw_image[:,:,3]
	image = raw_image[:,:,:3]
else:
	imgAlpha = np.ones(raw_image.shape[:2], dtype='uint8') * 255
	image = raw_image


def extractChannel(src, chIdx):# Uses [image, cv2]
    ### Extract channels and invert them
    maskCh = 255 - src[:,:,chIdx]
    ### ... or not. Tried at end again, and yes, no invert
    if mode == "Additive":
        maskCh = src[:,:,chIdx]
    
    ### Stretch to same shape as imgMain
    if (maskCh.shape[:2] != image.shape[:2]):
        #maskCh = cv2.resize(maskCh, image.shape[:2], interpolation=cv2.INTER_NEAREST)
        maskCh = cv2.resize(maskCh, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_NEAREST)
    ### Widen into 3-Channel image again
    maskChX = cv2.merge([maskCh, maskCh, maskCh])
    #cv2.imshow('Channel '+str(chIdx)+ ': ', maskChX) 

    return maskChX
#-----
#cv2.destroyAllWindows()

maskB = extractChannel(mask, 0) ## Pink == Color 3
maskG = extractChannel(mask, 1) ## Yellow == Color 1
maskR = extractChannel(mask, 2) ## Red == Color 2... Last pic says that red might be G...

#### Make colors stronger before being toned down again
#hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
#hsv[:,:,1] = hsv[:,:,1] + 10
#image = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
#if show: cv2.imshow('Stronger', image)

#### Apply color per channel
bitmaskArr = []
def applyColor(_mask, _colArr, tag): ## read: [show, np, cv2, mode], write: [bitmaskArr]
	"""
	_mask :: One Color channel of [imgMask] as BW, extended into 3-Channel
	:: Only cv2.show & cv2.addWeighted need it as 3-Channel + Convenient for 'Additive'
	_colArr :: An [ R, G, B ] Array; Alpha is discarded
	
	Given a mask [0], apply an RGB color [1] where '[0].pixel > 0'
	"""
	if show: print(_colArr)
	#tag = str(_colArr[0])
	## Make a white image to create a mask for "above 0"
	bitmask = np.ones(_mask.shape[:2], dtype="uint8") * 255
	bitmask[:,:] = (_mask[:,:,0] != 0)
	bitmask = cv2.merge([bitmask*255, bitmask*255, bitmask*255])
	if show: cv2.imshow('bitmask'+tag, bitmask) ## Where to add color
	bitmaskArr.append(bitmask)
	
	## Create an image of this color
	colImg0 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[0]
	colImg1 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[1]
	colImg2 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[2]
	colImg = cv2.merge([colImg2, colImg1, colImg0]) ## Apparently the KK-RGB is as BGR ???
	if show: cv2.imshow('Color'+tag, colImg)  ## A canvas of this Color
	if show: cv2.imshow('ColorMask'+tag, _mask) ## How the channel looks
	
	## Apply that color
	if mode == "Overlay":
		_mask = cv2.addWeighted(_mask, beta, colImg, alpha, 0)
	elif mode == "Additive":
		#print(_colArr[0], " -> ", _colArr[0] / 255)
		#print((_mask[0,0,:]))
		#print((_mask[0,0,:] / 255))
		#print((_mask[0,0,:] / 255) * _colArr)
		#print((_mask[0,0,:]) * (_colArr / 255))
		_mask[:,:,0] = ((_mask[:,:,0] / 255) * (colImg[:,:,0]))
		_mask[:,:,1] = ((_mask[:,:,1] / 255) * (colImg[:,:,1]))
		_mask[:,:,2] = ((_mask[:,:,2] / 255) * (colImg[:,:,2]))
	if show: cv2.imshow('Unmasked + Color:'+tag, _mask)
	
	## Apply mask again
	return np.bitwise_and(bitmask, _mask)

if flagBlue:
	applyColor(maskB, colB_3Pink, "B")
	if show: cv2.imshow('Mask B: '+str(colB_3Pink), maskB)
maskG = applyColor(maskG, colG_1Yellow, "G")
if show: cv2.imshow('Mask G: '+str(colG_1Yellow), maskG)
maskR = applyColor(maskR, colR_2Red, "R")
if show: cv2.imshow('Mask R: '+str(colR_2Red), maskR)


"""
#### https://pythonhosted.org/blend_modes/
Soft Light    (blend_modes.soft_light)
Lighten Only  (blend_modes.lighten_only)
Dodge         (blend_modes.dodge)
Addition      (blend_modes.addition)
Darken Only   (blend_modes.darken_only)
Multiply      (blend_modes.multiply)
Hard Light    (blend_modes.hard_light)
Difference    (blend_modes.difference)
Subtract      (blend_modes.subtract)
Grain Extract (blend_modes.grain_extract, known from GIMP)
Grain Merge   (blend_modes.grain_merge, known from GIMP)
Divide        (blend_modes.divide)

"""


if mode == "Additive":
	if flagBlue:
		final = imglib.blend_segmented(blend_modes.addition, maskR, maskG, 1)
		final = imglib.blend_segmented(blend_modes.addition, final, maskB, 1)
	else:
		final = imglib.blend_segmented(blend_modes.addition, maskR, maskG, 1)
		if show: cv2.imshow('Combined ColorMask (float)', final)
		#print(final[:2,:2,0])
		#print(final[:2,:2,1])
		#print(final[:2,:2,2])
		#final = (final * 255)
elif mode == "Overlay":
	final = cv2.addWeighted(maskR, beta, maskG, alpha, 0)
#else: print("Free NotImplementedError for you")

if show: cv2.imshow('Final w/o Main (int)', final.astype("uint8"))

def converter(img): ## read: [imgAlpha, cv2]
	if img.shape[2] == 4:
		return (cv2.merge([img[:,:,0], img[:,:,1], img[:,:,2], img[:,:,3]]) / 255).astype(float)
	return (cv2.merge([img[:,:,0], img[:,:,1], img[:,:,2], imgAlpha]) / 255).astype(float)

### If a MainTex exists, apply the ColorMask to it
if (noMainTex):
	image = final
else:
	#print("img:{} final:{} beta:{} alpha:{}".format(image.shape, final.shape, beta, alpha))
	if image.shape[2] == 3 and final.shape[2] >= 4: ## Actually always bc 'final' always has alpha through 'converter'
		image = converter(image)#cv2.merge([image[:,:,0], image[:,:,1], image[:,:,2], imgAlpha])
		final = converter(final)
		if show: cv2.imshow('Final w/o Main (float)', final)
		#if has_alpha:
		#	#image = converter(image)#cv2.merge([image[:,:,0], image[:,:,1], image[:,:,2], imgAlpha])
		#	image = cv2.addWeighted(image, beta, final, alpha, 0)
		#	has_alpha = False ## Because already added
		#else:
		image = cv2.addWeighted(image[:,:,:3], beta, final[:,:,:3], alpha, 0) * 255
	else:
		image = cv2.addWeighted(image, beta, final, alpha, 0)

#### Remerge Alpha
if has_alpha: image = cv2.merge([image[:,:,0], image[:,:,1], image[:,:,2], imgAlpha.astype(float)])

if show: cv2.imshow('Final', image.astype("uint8"))
if show: k = cv2.waitKey(0) & 0xFF

## Short remark: If certain parts appear purple in [G]-Pictures but end up being "Green"
## Then the reason for this is that there was simply no [B] to handle the "Blue" part.
##### The "purple" might even be an error, as it only appears with float, but not with int
## The image written to disk will contain the 'purple', through.

### Write out final image
outName = imgMain[:-4] + "_pyCol.png"
if noMainTex: outName = imgMask[:-4] + "_pyCol.png"
cv2.imwrite(outName, image)
print("Wrote output image at\n" + outName)
