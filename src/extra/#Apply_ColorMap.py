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
if (argLen < 4):## Incl. the sys path to this file
	print("Must have at least 3 arguments")
	exit()

arguments_help = """
[1]: Path to MainTex   :: can be empty
[2]: Path to ColorMask :: IOError if not found
[3]: The first Color (R), used for red areas
[4]: The second Color (G), used for yellow areas
[5]: The third Color (B), used for pink areas
[6]: Options as JSON dictionary

3 4 5 are RGB or RGBA arrays mapped to 0...1
"""

#-------------
imgMain = sys.argv[1] ## MainTex.png
imgMask = sys.argv[2] ## ColorMask.png
#-------------
colR_1Red        = json.loads(sys.argv[3]) ##[isHair: Hair Base]
if argLen > 5:
	colG_2Yellow = json.loads(sys.argv[4]) ##[isHair: Hair Root]
	colB_3Pink   = json.loads(sys.argv[5]) ##[isHair: Hair Tip]
#-------------
data = {}
if (argLen > 6): data = imglib.TryLoadJson(sys.argv[6])
mode            = data.get("mode", None)
altname         = data.get("altName", "")
isHair          = data.get("hair", False)
verbose         = data.get("showinfo", False)
alphafactor     = data.get("saturation", 1)
#----------
if len(altname.strip()) == 0: altname = None
#----------

args = sys.argv[1:]
if verbose: print(("\n=== Running ColorMask Script with arguments:" + "\n-- %s" * len(args)) % tuple(args))
else: print("\n=== Running ColorMask Script")

#---------- Options
### Apply Transparency of 30% ( = 64 of 255)
alpha     = 1.0 #64 / 255    ## For mask
beta      = 1.0 - alpha ## For main
show      = False       ## Do cv2.imshow
opt = imglib.makeOptions(locals())

#---------- Set some flags
noMainTex    = len(imgMain.strip()) == 0
saturation   = max(0, min(1, 1 * alphafactor))
dev_invertG  = True; dev_invertB = True

def isUseful(arr):
	try:
		if arr is None: return False
		if len(arr) < 3: return False
		return all([a == 0 for a in arr]) == False
	except: return False
flagRed   = isUseful(colR_1Red)
flagGreen = isUseful(colG_2Yellow)
flagBlue  = isUseful(colB_3Pink)


### Read in pics
raw_image = None
mask = cv2.imread(imgMask)
if mask is None:
	raise IOError("Mask-File '{}' does not exist.".format(imgMask))

if (noMainTex): ## Color may not always have a mainTex
	image = np.ones(mask.shape[:2], dtype='uint8') * 255
	raw_image = cv2.merge([image, image, image])
	image = None
else:
	raw_image = cv2.imread(imgMain, cv2.IMREAD_UNCHANGED)
	if raw_image is None:
		raise IOError(f"MainTex '{imgMain}' was provided but is invalid!")
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
##-- KK ColorMask is in BGR Format
maskB = extractChannel(mask, 0) ## Pink   == Color 3
maskG = extractChannel(mask, 1) ## Yellow == Color 2
maskR = extractChannel(mask, 2) ## Red    == Color 1

#### Apply color per channel
bitmaskArr = []
showCol = show and False
def applyColor(_mask, _colArr, tag, invert=False): ## read: [show, np, cv2, mode], write: [bitmaskArr]
	"""
	_mask :: One Color channel of [imgMask] as BW, extended into 3-Channel
	:: Only cv2.show & cv2.addWeighted need it as 3-Channel + Convenient for 'Additive'
	_colArr :: An [ R, G, B ] Array; Alpha is discarded
	invert  :: Boolean to generate inverted color
	
	Given a mask [0], apply an RGB color [1] where '[0].pixel > 0'
	"""
	if showCol: print(_colArr)
	if invert: _colArr = imglib.invertCol(_colArr)
	
	## Make a white image to create a mask for "above 0"
	bitmask = np.ones(_mask.shape[:2], dtype="uint8") * 255
	bitmask[:,:] = (_mask[:,:,0] != 0)
	bitmask = cv2.merge([bitmask*255, bitmask*255, bitmask*255])
	if showCol: DisplayWithAspectRatio(opt, tag+'-bitmask', bitmask, 256) ## Where to add color
	bitmaskArr.append(bitmask)
	
	## Create an image of this color
	colImg0 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[0]
	colImg1 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[1]
	colImg2 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[2]
	colImg = cv2.merge([colImg2, colImg1, colImg0]) ## KK ColorMask is BGR
	if showCol: DisplayWithAspectRatio(opt, tag+'-Color', colImg, 256)    ## A canvas of this Color
	if showCol: DisplayWithAspectRatio(opt, tag+'-ColorMask', _mask, 256) ## How the channel looks
	#>> State: A BlackWhite Image of the DetailMap-Layer \\[HSV]: 'V' maps the corresponding Alpha
	
	#imglib.testOutModes_wrap(colImg, _mask)
	
	_mask[:,:,0] = ((_mask[:,:,0] / 255) * (colImg[:,:,0]))
	_mask[:,:,1] = ((_mask[:,:,1] / 255) * (colImg[:,:,1]))
	_mask[:,:,2] = ((_mask[:,:,2] / 255) * (colImg[:,:,2]))
	#_mask = imglib.blend_segmented(blend_modes.addition, _mask / 255, colImg, alpha)
	if showCol: DisplayWithAspectRatio(opt, tag+'-NoMask+Color', _mask, 256)
	#>> State: Colorize the mask \\[HSV]: Set H,S from color, then scale Color.V based on Mask.V 
	
	## Apply mask again to cut out any potential color artifacts
	return np.bitwise_and(bitmask, _mask)

maskG = applyColor(maskG, colG_2Yellow, "G", dev_invertG)
if showCol: DisplayWithAspectRatio(opt, 'Mask G', maskG, 256)
maskR = applyColor(maskR, colR_1Red, "R")
if showCol: DisplayWithAspectRatio(opt, 'Mask R', maskR, 256)

if flagBlue:
	maskB = applyColor(maskB, colB_3Pink, "B", dev_invertB)
	if showCol: DisplayWithAspectRatio(opt, 'Mask B', maskB, 256)

### Get all black spots in the mask
# Only R: Normal, Hard_light
# Only G: Ovl, Dodge, Div, Soft_Light, Sub
# [G] + B where both W: Multiply, Darken
# [R] + W where either W: Screen, Lighten, Add
# Add inverted G to R: Diff
# Keep where equal, average where not: GMerge
# Grey where both same, B for B on W, W for W on B: GExtract
###
##-- Combine Masks
bitmask = imglib.blend_segmented(blend_modes.addition, bitmaskArr[0], bitmaskArr[1], 1)
if flagBlue: bitmask = imglib.blend_segmented(blend_modes.addition, bitmask, bitmaskArr[2], 1)

##-- Invert to mask out part of image later on
tmp = np.ones(bitmask.shape, dtype="uint8") * 255
inverted = imglib.blend_segmented(blend_modes.difference, tmp, bitmask, 1)
keeper = imglib.blend_segmented(blend_modes.multiply, image, inverted, 1)

"""
#### https://pythonhosted.org/blend_modes/
Normal        (blend_modes.normal)
Soft Light    (blend_modes.soft_light)
Lighten Only  (blend_modes.lighten_only)
Dodge         (blend_modes.dodge)
Addition      (blend_modes.addition)
Darken Only   (blend_modes.darken_only)
Multiply      (blend_modes.multiply) -- a * b
Screen        (blend_modes.screen)   -- [inverse multiply]
Hard Light    (blend_modes.hard_light)
Difference    (blend_modes.difference)
Subtract      (blend_modes.subtract)
Grain Extract (blend_modes.grain_extract, known from GIMP)
Grain Merge   (blend_modes.grain_merge, known from GIMP)
Divide        (blend_modes.divide)
Overlay       (blend_modes.overlay)
"""

is_dark = False

if True:
	## Hair: Red:Red = Base, Yellow:Green = Root, Pink:Blue = Tips
	x_Mode     = blend_modes.difference if is_dark else blend_modes.overlay
	if dev_invertG: x_Mode = blend_modes.difference
	x_ModeBlue = blend_modes.difference if is_dark else blend_modes.hard_light
	if mode is not None: x_Mode = mode
	
	### Convert to BW, convert into alpha, use that as bitmask for mixing
	if not dev_invertG: maskG = imglib.apply_alpha_BW(opt, maskG).astype("uint8")
	
	final = imglib.blend_segmented(x_Mode, maskR, maskG, 1)
	##-- If Mask contains a Pink Layer, apply the hair tip gradient
	if flagBlue:
		if show: DisplayWithAspectRatio(opt, '[hair] Pre-Blue', final, 256)
		if not dev_invertB: maskB = imglib.apply_alpha_BW(opt, maskG).astype("uint8")
		if show: DisplayWithAspectRatio(opt, '[hair] Prepare Blue', maskB, 256)
		final = imglib.blend_segmented(x_Mode, final, maskB, saturation)
		#if show: DisplayWithAspectRatio(opt, '[hair] Post-blue', final, 256)
else:#elif noMainTex:### Works for: [acs_m_accZ4601: German Cross], only two colors
	## Will look ugly on gradient colors
	final = imglib.combineWithBitmask(opt, maskR, maskG, bitmaskArr[0])
	if flagBlue:
		if show: DisplayWithAspectRatio(opt, '[NT] Pre-Blue', final, 256)
		final = imglib.combineWithBitmask(opt, final, maskB, bitmaskArr[2])

### If no MainTex exists, use the ColorMask directly
if (noMainTex):
	DisplayWithAspectRatio(opt, '[I] Final no Main', final.astype("uint8"), 256)
	image = final
else: ### Otherwise apply the ColorMask to it
	if show: DisplayWithAspectRatio(opt, '[I] Pre-merge', image, 256)
	image = imglib.blend_segmented(blend_modes.multiply, image, final, 1)

### Apply the non-affected parts back.
image = imglib.blend_segmented(blend_modes.screen, image, keeper, 1)

#### Remerge Alpha
if has_alpha:
	DisplayWithAspectRatio(opt, 'Pre-alpha', image.astype("uint8"), 256)
	image = cv2.merge([image[:,:,0], image[:,:,1], image[:,:,2], imgAlpha.astype(float)])

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
