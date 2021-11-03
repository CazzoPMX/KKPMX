import cv2
import numpy as np
import sys,os
import json
import blend_modes

try:
	from kkpmx_image_lib import DisplayWithAspectRatio, DisplayWithAspectRatio_f
	import kkpmx_image_lib as imglib
except ImportError as eee:
	from . import kkpmx_image_lib as imglib
	DisplayWithAspectRatio = imglib.DisplayWithAspectRatio
	DisplayWithAspectRatio_f = imglib.DisplayWithAspectRatio_f

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

args = sys.argv[1:]

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

data = {}
if (argLen > 6): data = json.loads(sys.argv[6])
mode            = data.get("mode", "Overlay")
altname         = data.get("altName", "")
useBrightColors = data.get("bright", False)
isHair          = data.get("hair", False)
verbose         = data.get("showinfo", False)
if len(altname) == 0: altname = None
#----------

if verbose: print(("\n=== Running ColorMask Script with arguments:" + "\n-- %s" * len(args)) % tuple(args))
else: print("\n=== Running ColorMask Script")

#---------- Flags
### Apply Transparency of 30% ( = 64 of 255)
alpha     = 64 / 255    ## For mask
beta      = 1.0 - alpha ## For main
show      = False       ## Do cv2.imshow
noMainTex = len(imgMain) == 0
opt = imglib.makeOptions(locals())

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
	DisplayWithAspectRatio(opt, 'Org', raw_image, 256)



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
    #DisplayWithAspectRatio(opt, 'Channel '+str(chIdx)+ ': ', maskChX) 

    return maskChX
#-----
cv2.destroyAllWindows()

maskB = extractChannel(mask, 0) ## Pink == Color 3
maskG = extractChannel(mask, 1) ## Yellow == Color 1
maskR = extractChannel(mask, 2) ## Red == Color 2... Last pic says that red might be G...

#### Make colors stronger before being toned down again
#hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
#hsv[:,:,1] = hsv[:,:,1] + 10
#image = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
#if show: DisplayWithAspectRatio(opt, 'Stronger', image)

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
	if show: DisplayWithAspectRatio(opt, tag+'-bitmask', bitmask, 256) ## Where to add color
	bitmaskArr.append(bitmask)
	
	## Create an image of this color
	colImg0 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[0]
	colImg1 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[1]
	colImg2 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[2]
	colImg = cv2.merge([colImg2, colImg1, colImg0]) ## Apparently the KK-RGB is as BGR ???
	if show: DisplayWithAspectRatio(opt, tag+'-Color', colImg, 256)  ## A canvas of this Color
	if show: DisplayWithAspectRatio(opt, tag+'-ColorMask', _mask, 256) ## How the channel looks
	
	#imglib.testOutModes_wrap(colImg, _mask)
	
	## Apply that color
	if mode == "Overlay":
		#_mask = cv2.addWeighted(_mask, beta, colImg, alpha, 0)
		_mask = imglib.blend_segmented(blend_modes.overlay, _mask, colImg, 1)
	elif mode == "Additive":
		_mask[:,:,0] = ((_mask[:,:,0] / 255) * (colImg[:,:,0]))
		_mask[:,:,1] = ((_mask[:,:,1] / 255) * (colImg[:,:,1]))
		_mask[:,:,2] = ((_mask[:,:,2] / 255) * (colImg[:,:,2]))
		#_mask = imglib.blend_segmented(blend_modes.addition, _mask / 255, colImg, alpha)
	if show: DisplayWithAspectRatio(opt, tag+'-NoMask+Color', _mask, 256)
	
	## Apply mask again
	return np.bitwise_and(bitmask, _mask)

maskG = applyColor(maskG, colG_1Yellow, "G")
if show: DisplayWithAspectRatio(opt, 'Mask G: '+str(colG_1Yellow), maskG, 256)
maskR = applyColor(maskR, colR_2Red, "R")
if show: DisplayWithAspectRatio(opt, 'Mask R: '+str(colR_2Red), maskR, 256)

if flagBlue:
	applyColor(maskB, colB_3Pink, "B")
	if show: DisplayWithAspectRatio(opt, 'Mask B: '+str(colB_3Pink), maskB, 256)

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
	#imglib.testOutModes_wrap(maskR, maskG)
	if isHair:### Works for:
		### Convert to BW, convert into alpha, use that as bitmask for mixing
		bwGreen = imglib.convert_to_BW(maskG, False)
		maskG = imglib.converterScaled(opt, maskG, bwGreen, True).astype("uint8")
		final = imglib.blend_segmented(blend_modes.difference, maskR, maskG, 1)
		if flagBlue:
			bwBlue = imglib.convert_to_BW(maskB, False)
			maskB = imglib.converterScaled(opt, maskB, bwBlue, True).astype("uint8")
			final = imglib.blend_segmented(blend_modes.difference, final, maskB, 1)
	elif noMainTex:### Works for: [acs_m_accZ4601: German Cross], only two colors
		final = imglib.combineWithBitmask(opt, maskR, maskG, bitmaskArr[0])
		if flagBlue:
			final = imglib.combineWithBitmask(opt, final, maskB, bitmaskArr[2])
	else:
		final = imglib.blend_segmented(blend_modes.normal, maskR, maskG, alpha)
		if flagBlue:
			final = imglib.blend_segmented(blend_modes.normal, final, maskB, alpha)
	if show: DisplayWithAspectRatio(opt, '[F] CM Additive', final, 256)
elif mode == "Overlay":
	final = cv2.addWeighted(maskR, beta, maskG, alpha, 0)

DisplayWithAspectRatio(opt, '[I] Final w/o Main', final.astype("uint8"), 256)

def converter(img): ## read: [imgAlpha, cv2]
	if img.shape[2] == 4:
		return (cv2.merge([img[:,:,0], img[:,:,1], img[:,:,2], img[:,:,3]]) / 255).astype(float)
	return (cv2.merge([img[:,:,0], img[:,:,1], img[:,:,2], imgAlpha]) / 255).astype(float)

### If a MainTex exists, apply the ColorMask to it
if (noMainTex):
	image = final
else:
	#print("img:{} final:{} beta:{} alpha:{}".format(image.shape, final.shape, beta, alpha))
	#if image.shape[2] == 3 and final.shape[2] >= 4: ## Actually always bc 'final' always has alpha through 'converter'
	if useBrightColors:
		#imglib.testOutModes_wrap(image, final)
		image = converter(image)#cv2.merge([image[:,:,0], image[:,:,1], image[:,:,2], imgAlpha])
		final = converter(final)
		DisplayWithAspectRatio(opt, '[F] Image w/o Mask', image*255, 256)
		DisplayWithAspectRatio(opt, '[F] Final w/o Main', final*255, 256)
		#if has_alpha:
		#	#image = converter(image)#cv2.merge([image[:,:,0], image[:,:,1], image[:,:,2], imgAlpha])
		#	image = cv2.addWeighted(image, beta, final, alpha, 0)
		#	has_alpha = False ## Because already added
		#else:
		#imglib
		#imglib.testOutModes_wrap((image[:,:,:3] * 255).astype('uint8'), (final[:,:,:3] * 255).astype('uint8'))
		image = cv2.addWeighted(image[:,:,:3], beta, final[:,:,:3], alpha, 0) * 255
	else:
		DisplayWithAspectRatio(opt, '[I] Image w/o Mask', image, 256)
		DisplayWithAspectRatio(opt, '[I] Final w/o Main', final, 256)
		image = imglib.blend_segmented(blend_modes.normal, image, final, 1)


#### Remerge Alpha
if has_alpha: image = cv2.merge([image[:,:,0], image[:,:,1], image[:,:,2], imgAlpha.astype(float)])

DisplayWithAspectRatio(opt, 'Final', image.astype("uint8"), 256)
if show: k = cv2.waitKey(0) & 0xFF

## Short remark: If certain parts appear purple in [G]-Pictures but end up being "Green"
## Then the reason for this is that there was simply no [B] to handle the "Blue" part.
##### The "purple" might even be an error, as it only appears with float, but not with int
## The image written to disk will contain the 'purple', through.

### Write out final image
outName = imgMain[:-4] + "_pyCol.png"
if noMainTex: outName = imgMask[:-4] + "_pyCol.png"
if altname is not None: outName = os.path.join(os.path.split(outName)[0], altname + "_pyCol.png")
cv2.imwrite(outName, image)
print("Wrote output image at\n" + outName)
