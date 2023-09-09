import cv2
import numpy as np
import sys,os
import json
import blend_modes
from copy import deepcopy

try:
	from kkpmx_image_lib import DisplayWithAspectRatio, DisplayWithAspectRatio_f
	import kkpmx_image_lib as imglib
except ImportError as eee:
	from . import kkpmx_image_lib as imglib
	DisplayWithAspectRatio = imglib.DisplayWithAspectRatio
	DisplayWithAspectRatio_f = imglib.DisplayWithAspectRatio_f

todos="""

Mask-R loses Mask-B (if B is different color)
Mask-B shows inverted color (if different color)
Mask-G shows inverted color (if same color)

if G and R have the same color, merge the masks and color both together
: Otherwise there is a weird shaded border in Test1B & Final

Still shows Test2A & Test3A if the Mask is full Black
: as well as running the Mask calc to begin with
:	Make sure that access to it is guarded by flags or turned into isAllSame

If G has weird borders, they are visible on Test1B as well
Rename the Test Windows to be better
Figure out and redocument the ColorMask being resized
: Also ignore doing that if all colors are the same anyway
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
altName         = data.get("altName", "")
isHair          = data.get("hair", False)
verbose         = data.get("showinfo", False)
alphafactor     = data.get("saturation", 1)
tex_scale       = data.get("scale", None)
tex_offset      = data.get("offset", None)
EX_no_invert    = data.get("noInvert", False)
#----------
if len(altName.strip()) == 0: altName = None
#----------

args = sys.argv[1:]
if verbose: print(("\n=== Running ColorMask Script with arguments:" + "\n-- %s" * len(args)) % tuple(args))
else: print("\n=== Running ColorMask Script")
######
## Help
#	'channel' := respective RGB channel of image (mask or target)
#	:: Only if not all three equal
#	::--- Per Color channel
#	:	*-bitmask:		Binary image of Channel Mask
#	:	*-Color:		Color canvas of respective entry
#	:	*-ColorMask:	Grayscale image of Channel Mask
#	:	*-NoMask+Color:	Masked Color without constrained by bitmask
#	:	Mask *:			Masked Color after being cut by bitmask
#	::--- Once
#	:	Pre-Blue:		if 3rd channel, how the image looks with R+G combined incl BW handling
#	:	Prepare Blue:	if 3rd channel, what will be applied to the above image
#	:: If all three colors are equal
#	:	*-bitmask:		Binary image of each Channel Mask
#	:	ColorImgAll:	Color canvas of common color, without being cut by black parts
#	:: If no Main Tex exists
#	:	Final no Main:	Result of merging all channels
#	:: If a Main Tex exists
#	:	[I] Pre Merge:	The base image before being combined with the merged channels
#	::--- If it had an alpha channel
#	:	Pre-alpha:		The combined image, before restoring the alpha channel
#	Final:				The final result that will be persisted on disk

#---------- Options
### Apply Transparency of 30% ( = 64 of 255)
alpha     = 1.0 #64 / 255    ## For mask
beta      = 1.0 - alpha ## For main
show      = False       ## Do cv2.imshow
opt = imglib.makeOptions(locals())

#---------- Set some flags
noMainTex    = len(imgMain.strip()) == 0
saturation   = max(0, min(1, 1 * alphafactor))
#dev_invertG  = True; dev_invertB = True
dev_invertG  = False; dev_invertB = False; dev_testOff = True

if isHair:### FIX IT FOR HAIR LATER -- Note: It worked just fine before, so this is a PATCHFIX to revert changes
	# That Xmas Ribon looked better too before
	dev_invertG = True
	dev_invertB = True
	dev_testOff = False

def isUseful(arr):
	try:
		if arr is None: return False
		if len(arr) < 3: return False
		return all([a == 0 for a in arr]) == False
	except: return False
flagRed   = isUseful(colR_1Red)
flagGreen = isUseful(colG_2Yellow)
flagBlue  = isUseful(colB_3Pink)
isAllSame = False
if flagRed and flagGreen and flagBlue:
	isAllSame = colR_1Red == colG_2Yellow == colB_3Pink
elif flagRed and not flagGreen and not flagBlue: isAllSame = True
def cmpCol(arr1, arr2):
	return arr1[0] == arr2[0] and arr1[1] == arr2[1] and arr1[2] == arr2[2]

flagGreenIsRed = flagGreen and flagRed and cmpCol(colR_1Red, colG_2Yellow)
flagBlueIsRed  = flagBlue and flagRed and cmpCol(colR_1Red, colB_3Pink)
isAllSame = isAllSame or (flagGreenIsRed and flagBlueIsRed)
isAllSame = isAllSame or (not flagBlue and flagGreenIsRed)
##--[TODO] Nice and good, but I need to find a better solution later on.
flagGreenIsRed   = False
flagBlueIsRed    = False
flagIsFullYellow = False
flagIsFullPink   = False

### Read in pics
raw_image = None
mask = cv2.imread(imgMask)
if mask is None:
	raise IOError("Mask-File '{}' does not exist.".format(imgMask))

if (noMainTex): ## Color may not always have a mainTex
	image = np.full(mask.shape[:2], 255, dtype='uint8')
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
	imgAlpha = np.full(raw_image.shape[:2], 255, dtype='uint8')
	image = raw_image

#### Apply Scale and Offset
if tex_offset is not None:
	mask = imglib.roll_by_offset(mask, tex_offset, { "show": show })

if tex_scale is not None:
	mask = imglib.repeat_rescale(mask, tex_scale, { "show": show })
###--------
channelSum = { 0: 0, 1: 0, 2: 0 }
def extractChannel(src, chIdx):# Uses [image, cv2]
    ### Extract channels and invert them
    #maskCh = 255 - src[:,:,chIdx]
    ### ... or not. Tried at end again, and yes, no invert
    maskCh = src[:,:,chIdx]
    mySum = np.sum(maskCh)
    if show: print(f'{chIdx} has {mySum}')# 203.125.429 aka within 10
    channelSum[chIdx] = mySum
    
    ### Stretch to same shape as imgMain
    if (maskCh.shape[:2] != image.shape[:2]):
        #maskCh = cv2.resize(maskCh, image.shape[:2], interpolation=cv2.INTER_NEAREST)
        maskCh = cv2.resize(maskCh, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_NEAREST)
    ### Widen into 3-Channel image again
    maskChX = cv2.merge([maskCh, maskCh, maskCh])
    DisplayWithAspectRatio(opt, 'xChannel '+str(chIdx)+ ': ', maskChX, 256) 
    return maskChX
#-----
cv2.destroyAllWindows()
##-- KK ColorMask is in BGR Format
maskB = extractChannel(mask, 0) ## Pink   == Color 3
maskG = extractChannel(mask, 1) ## Yellow == Color 2
maskR = extractChannel(mask, 2) ## Red    == Color 1


#----- Had some assets doing this kind of weirdness, so lets support it
sumB_Pin = channelSum[0]
sumG_Yel = channelSum[1]
sumR_Red = channelSum[2]
if sumB_Pin == 0: ## About 97% on 1024x1024
	if (min([sumG_Yel, sumR_Red]) / max([sumG_Yel, sumR_Red])) > 0.95:
		flagIsFullYellow = True
elif sumG_Yel == 0:
	## About 97% on 1024x1024
	if (min([sumB_Pin, sumR_Red]) / max([sumB_Pin, sumR_Red])) > 0.95:
		flagIsFullPink = True

#### Apply color per channel
bitmaskArr = {}
colMapArr = {}
bwMapArr = {}
showCol = show and True
def getBMbyTag(tag):
	if tag == "G": return bitmaskArr["G"]
	if tag == "R": return bitmaskArr["R"]
	if tag == "B" and flagBlue: return bitmaskArr["B"]

colBW = {'B': -2, 'G': -2, 'R': -2}
COLB = imglib.BWTypes.BLACK
COLD = imglib.BWTypes.DARK
COLW = imglib.BWTypes.WHITE

def invertColorIfApplicable(_colArr, tag, invert):
	if isHair:
		if not EX_no_invert or True:
			invert = imglib.lazy_color_check(_colArr, colBW[tag], invert)
			if invert and colBW[tag] is not COLW: _colArr = imglib.invertCol(_colArr)
			elif colBW[tag] in [COLB,COLD]:       _colArr = imglib.invertCol(_colArr)
	else:
		if colBW[tag] is COLB:              _colArr = imglib.invertCol(_colArr)
	return _colArr

def applyColor(_mask, _colArr, tag, invert=False, bitmaskOnly=False): ## read: [show, np, cv2, mode], write: [bitmaskArr]
	"""
	_mask :: One Color channel of [imgMask] as BW, extended into 3-Channel
	:: Only cv2.show & cv2.addWeighted need it as 3-Channel + Convenient for 'Additive'
	_colArr :: An [ R, G, B ] Array; Alpha is discarded
	invert  :: Boolean to generate inverted color
	
	Given a mask [0], apply an RGB color [1] where '[0].pixel > 0'
	"""
	if showCol: print(f"Apply Tag[{tag}]: {_colArr}")
	colBW[tag] = imglib.color_is_BW(_colArr)
	
	 ## Don't turn white into black, and make black into white regardless
	#if isHair:
	#	if not EX_no_invert or True:
	#		if invert and colBW[tag] is not COLW: _colArr = imglib.invertCol(_colArr)
	#		elif colBW[tag] in [COLB,COLD]:       _colArr = imglib.invertCol(_colArr)
	#else:
	#	if colBW[tag] is COLB:              _colArr = imglib.invertCol(_colArr)
	_colArr = invertColorIfApplicable(_colArr, tag, invert)
	if showCol: print(f">> {_colArr} bc {colBW[tag]}")
	
	## Make a white image to create a mask for "above 0"
	bitmask = np.ones(_mask.shape[:2], dtype="uint8") * 255
	bitmask[:,:] = (_mask[:,:,0] != 0)
	bitmask = cv2.merge([bitmask*255, bitmask*255, bitmask*255])
	if showCol: DisplayWithAspectRatio(opt, tag+'-bitmask', bitmask, 256) ## Where to add color
	bitmaskArr[tag] = bitmask
	
	##-- Interesting Effect when this line is commented out
	if "G" in bwMapArr and tag == "R":
		if flagGreenIsRed: _mask = _mask + bwMapArr["G"]
		else: _mask = _mask - bwMapArr["G"] ## Also still hard cut on this one
	if "B" in bwMapArr and tag == "R": 
		if flagBlueIsRed: _mask = _mask + bwMapArr["B"]
		else: _mask = _mask - bwMapArr["B"] ## Also still hard cut on this one
	
	bwMapArr[tag] = deepcopy(_mask)
	if bitmaskOnly: return bitmask
	
	## Create an image of this color
	colImg0 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[0]
	colImg1 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[1]
	colImg2 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[2]
	colImg = cv2.merge([colImg2, colImg1, colImg0]) ## KK ColorMask is BGR
	if showCol: DisplayWithAspectRatio(opt, tag+'-Color', colImg, 256)    ## A canvas of this Color
	if showCol: DisplayWithAspectRatio(opt, tag+'-ColorMask', _mask, 256) ## How the channel looks (the Mask Channel but including Gradients)
	#>> State: A BlackWhite Image of the DetailMap-Layer \\[HSV]: 'V' maps the corresponding Alpha
	
	colMapArr[tag] = deepcopy(colImg)
	#imglib.testOutModes_wrap(colImg, _mask)
	
	_mask[:,:,0] = ((_mask[:,:,0] / 255) * (colImg[:,:,0]))
	_mask[:,:,1] = ((_mask[:,:,1] / 255) * (colImg[:,:,1]))
	_mask[:,:,2] = ((_mask[:,:,2] / 255) * (colImg[:,:,2]))
	#_mask = imglib.blend_segmented(blend_modes.addition, _mask / 255, colImg, alpha)
	if showCol: DisplayWithAspectRatio(opt, tag+'-NoMask+Color', _mask, 256)
	#>> State: Colorize the mask \\[HSV]: Set H,S from color, then scale Color.V based on Mask.V 
	
	## Apply mask again to cut out any potential color artifacts
	return np.bitwise_and(bitmask, _mask)

##-- Old
if not isAllSame:
	maskG = applyColor(maskG, colG_2Yellow, "G", dev_invertG)
	if showCol: DisplayWithAspectRatio(opt, 'Mask G', maskG, 256)
	maskR = applyColor(maskR, colR_1Red, "R")
	if showCol: DisplayWithAspectRatio(opt, 'Mask R', maskR, 256)
	
	if flagBlue:
		maskB = applyColor(maskB, colB_3Pink, "B", dev_invertB)
		if showCol: DisplayWithAspectRatio(opt, 'Mask B', maskB, 256)
else:
#if isAllSame:
	## Just get the bitmask of the whole mask
	#if (mask.shape[:2] != image.shape[:2]):
	#	mask = cv2.resize(mask, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_NEAREST)
	bitmask = np.ones(mask.shape[:2], dtype="uint8") * 255
	bitmask[:,:] = (mask[:,:,0] != 0)
	bitmask = cv2.merge([bitmask*255, bitmask*255, bitmask*255])
	applyColor(maskG, colG_2Yellow, "G", dev_invertG, bitmaskOnly=True)
	applyColor(maskR, colR_1Red, "R", bitmaskOnly=True)
	if flagBlue: applyColor(maskB, colB_3Pink, "B", dev_invertB, bitmaskOnly=True)
	
	if showCol: DisplayWithAspectRatio(opt, 'All'+'-bitmask', bitmask, 256) ## Where to add color
	#bitmaskArr.append(bitmask)
	##-- And produce a single full block of the correct color.
	final = imglib.getColorImg(opt, maskR, colR_1Red, "All", True)

### Get all black spots in the mask
# Only R: Normal, Hard_light
# Only G: Ovl, Dodge, Div, Soft_Light, Sub
# [G] + B where both W: Multiply, Darken
# [R] + W where either W: Screen, Lighten, Add
# Add inverted G to R: Diff
# Keep where equal, average where not: GMerge
# Grey where both same, B for B on W, W for W on B: GExtract
###
##-- Combine Masks to cut out parts that are unaffected in all channels
bitmask = imglib.blend_segmented(blend_modes.addition, getBMbyTag("G"), getBMbyTag("R"), 1)
if flagBlue: bitmask = imglib.blend_segmented(blend_modes.addition, bitmask, getBMbyTag("B"), 1)

tmp = np.full(bitmask.shape, 255, dtype="uint8")
#imglib.testOutModes_wrap(tmp, bitmask, msg="Tmp + BitMask")
inverted = imglib.blend_segmented(blend_modes.difference, tmp, bitmask, 1)
#imglib.testOutModes_wrap(image, inverted, msg="image + inverted")
keeper = imglib.blend_segmented(blend_modes.multiply, image, inverted, 1)
keeper = imglib.apply_alpha_BW(opt, keeper.astype("uint8")).astype("uint8") #Verified for Hair + DARKxDARK
DisplayWithAspectRatio(opt, 'keeper', keeper, 256)


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

inverted_RG = False
overwriteMode = False
isInBlue = False ## Basically means "Hairtip only"

treatAsHair = isHair
if not isHair:
	nameCheck = altName if altName is not None else os.path.split(imgMask)[1]
	tailArr = ["acs_m_fox", "arai_tail"]
	for tail in tailArr:
		if tail in nameCheck:
			treatAsHair = True
			break

def handle_BW(_base, _mask, tag, tagB=None):
	## Probably make Splitter with (all fields, anyNorm(DARK,NORM,BRIGHT,None), anyLow(BLACK,DARK), anyHigh(WHITE,BRIGHT))
	isWhite = colBW[tag] == imglib.BWTypes.WHITE
	isBlack = colBW[tag] == imglib.BWTypes.BLACK
	isNorma = colBW[tag] == imglib.BWTypes.NORM
	isDark  = colBW[tag] == imglib.BWTypes.DARK
	isBrigt = colBW[tag] == imglib.BWTypes.BRIGHT
	
	BisNone  = tagB is None
	BisWhite = False if tagB is None else colBW[tagB] == imglib.BWTypes.WHITE
	BisBlack = False if tagB is None else colBW[tagB] == imglib.BWTypes.BLACK
	BisNorma = False if tagB is None else colBW[tagB] == imglib.BWTypes.NORM
	BisDark  = False if tagB is None else colBW[tagB] == imglib.BWTypes.DARK
	_mode = x_Mode
	#if dev_testOff: _mode = blend_modes.screen
	__IsTesting = show and False#isInBlue#tagB != "GR"
	####
	# Normal: Plain replace \\ Mul: Masked color \\ Sub: Remove mask
	# GMerge:   Multiply Saturation * 1 - GreyValue (== Black means Color x2, White = White)
	# GExtract: Multiply Saturation * GreyValue (== Black means White, White = Color x2)
	# Overlay:  Increase Saturation with Black
	# Div:        White = Color, Middle = Cyan,  Black = White \\ Dodge == Inverse Div
	# Hard_light: White = White, Middle = Color, Black = Black
	# Screen:   Increase Luminosity with White
	if isWhite: _mode = blend_modes.screen
	if isBlack: _mode = blend_modes.screen
	if isDark and BisDark: _mode = blend_modes.screen ## Verified(Hair): Screen looks best
	if show:
		print(f"::[Mask {tag}]: Mode={_mode}, Tag={colBW[tag]}, W={isWhite}, B={isBlack}")
		print(f"::[Base {tagB}]: Mode={_mode}, Tag={colBW.get(tagB, None)}, W={BisWhite}, B={BisBlack}")
		
	##-- TODO: Do some things when both colors are exact equal
	
	if __IsTesting:
		DisplayWithAspectRatio(opt, f'DEV: BASE (Pre)', _base, 256)
		DisplayWithAspectRatio(opt, f'DEV: MASK (Pre)', _mask, 256)
		imglib.testOutModes_wrap(_base, _mask, msg="Before Any") ## #
	#:: <Brown 50> on <DarkBrown x2> -- Dodge looks fine
	#:: WHITE on WHITE: screen works
	#:: RED on <WHITE+WHITE>: (Screen, Difference, Add) work to keep Red and WHITE -- using Difference
	#:: NORM on WHITE: !!screen keeps WHITE, difference inverts the wrong thing -- Normal & Mul add the Black too
	#:: NORM on <BAD NORM>: Screen&Add removes Mask, Difference adds it correctly
	#:: NORM on <OK NORM>: Screen&Add are correct Mask, Difference adds it a weird line ? << Difference
	#Verified: We don't even enter this on ALLSAME with NORM
	targetBM = None
	invertFinal = False
	#if isHair and not isInBlue: colBW["GR"] = colBW[tagB]	## Probably breaks lots of things if I add this now
	
	if (
		(isBlack and (BisNorma or BisWhite))  ## Verified(Tongue): Is G-R-B = BLACK on (BLACK on NORM): Starts pink, stays Pink
		or (isDark and BisNorma and isHair)
		): ## Test Shizoku
	
		## Test: BLACK on (WHITE on BLACK): (screen keeps B-WHITE in LightGray, Diff makes it BLACK) -- PostMerge the ALLBLACK parts keep original, which is white
		_base = imglib.invert(_base)
		invertFinal = True
	#elif isBlack and BisWhite: pass ## From Skull hairpin: BLACK on (BLACK on WHITE)
	elif isNorma and BisDark and isHair: ## Verified(Brown Hair 50 x 29x35)
		# Mask<Inv B> x Base(inv DARKxDARK into Inv = Ok) = Inv x None
		_mode = blend_modes.dodge ## Verified: No Invert needed, and (Brighter) is really brighter
	elif isWhite and BisWhite:
		colBW["GR"] = imglib.BWTypes.BLACK
		pass ## Verified: Nothing to be done on 255 x 255, but Screen is correct
	elif isNorma and BisBlack or (isDark and BisDark and isHair):
		## Verified: After combining NORM onto WHITE, we set it as BLACK and apply another NORM
		## Verified (DARK[2] at 29,35): Both HAIR are inverted by default, so add Mask as normal
		# --> So we just cut away the BitMask and invert it to apply as difference --> Works (although a bit weak in the color)
		_mask = imglib.apply_alpha_BW(opt, _mask).astype("uint8") #Verified for Hair + DARKxDARK
		#_mode = blend_modes.difference ## Keep it difference
		_mask = imglib.invert(_mask)
		## Verified: Still works with the above combo
		_base = imglib.invert(_base) ## By inverting Base as well, it works with Screen AND Difference
		if (isHair and isDark and BisDark):
			_mode = blend_modes.multiply ## Mask<29> is darker than Base<35>
			#>> Multiply: Much darker, similar to how KK overdoes it, but has proper Gradient
			#>> Dodge: Would at least add a Gradient when inverting Base as well....
			#_base = imglib.invert(_base); invertFinal = True ## ... but needs these two as well then, kinda TOO dark then
			colBW["GR"] = imglib.BWTypes.DARK
		else: invertFinal = True ## Verified(Hair + DARKxDARK gets no Invert)
	elif isNorma and BisWhite:
		## Verified: Combining NORM onto WHITE works by cutting out the originally white parts and reapply them so they get screened twice
		_tmp = imglib.invert(_base)
		#print(_tmp.shape)
		#print(_mask.shape)
		_tmp2 = imglib.invert(np.bitwise_and(getBMbyTag(tag), _base[:,:,:3].astype("uint8")))
		#imglib.testOutModes_wrap(_tmp, _tmp2, msg="Between invert and apply")
		#imglib.testOutModes_wrap(_tmp2, _tmp, msg="Between invert and apply")
		_base = imglib.blend_segmented(blend_modes.screen, _tmp, _tmp2, 1)
		### Verified: after this, tell the Blue Channel to treat this as Black
		colBW["GR"] = imglib.BWTypes.BLACK
	elif isWhite and BisBlack: ## From Xmas Ribbons G onto R
		#... Screen: G-WHITE stays white, R-BLACK stays BLACK -- R-WHITE x G-BLACK becomes Grey
		#... Diff:   G-WHITE becomes DarkGray, rest as above
		## TEST
		_mask = imglib.apply_alpha_BW(opt, _mask).astype("uint8")
		#_mode = blend_modes.difference ## Keep it difference
		_mask = imglib.invert(_mask)
		#_base = imglib.invert(_base) ## By inverting Base as well, it works with Screen AND Difference
		pass
	elif isBrigt and BisNone and treatAsHair and isInBlue:
		## [Lighten] on [base x maskInv] looks great, but color too bright
		## [Lighten] on [baseInv x maskInv] looks great, and color is a bit darker but still too off
		## --> Could be nice with finalInv + Mask with additional Lighten
		## isHair ++ [240, 25, 100]<Pink> onto [84 32 85]<MintGreen> //Ref: BRIGHT<LazyHack+Inv=False> vs. None<default> ###TestPattern
		## Pattern2: [237,212, 202]<Pink>: was NORM, now BRIGHT --> Should be inverted + Normal because background is unmasked black rest
		_mask = imglib.apply_alpha_BW(opt, _mask).astype("uint8")
		_mask = imglib.invert(_mask)
		DisplayWithAspectRatio(opt, f'DEV: MASK ({isInBlue})', _mask, 256)
		_mode = blend_modes.normal
		_base = imglib.invert(_base)
		invertFinal = True
		
		
	if overwriteMode: _mode = x_Mode
	
	_tmpInv=_tmpInv2=_mask2=_mask2Inv=None
	if __IsTesting:
		print(f"_mode is {_mode} -- Hair={isHair}, Blue={isInBlue}")
		imglib.testOutModes_wrap(_base, _mask, msg="Before apply (base x mask)")
		#imglib.testOutModes_wrap(_mask, _base, msg="Before apply (mask x base)")
		_tmpInv = imglib.invert(_base)
		imglib.testOutModes_wrap(_tmpInv, _mask, msg="Before apply (baseInv x mask)")
		## Base Inv + Mask(Color Inv) --> Mask would be too bright on (final Invert), Dodge again
		_tmpInv2 = imglib.invert(_mask)
		imglib.testOutModes_wrap(_base, _tmpInv2, msg="Before apply (base x maskInv)")
		imglib.testOutModes_wrap(_tmpInv, _tmpInv2, msg="Before apply (baseInv x maskInv)")
		#-----
		_mask2 = imglib.apply_alpha_BW(opt, _mask).astype("uint8") #Verified for Hair + DARKxDARK
		imglib.testOutModes_wrap(_base, _mask2, msg="Before apply (base x _mask2)")
		imglib.testOutModes_wrap(_tmpInv, _mask2, msg="Before apply (baseInv x _mask2)")
		_mask2 = imglib.invert(_mask2)
		imglib.testOutModes_wrap(_base, _mask2, msg="Before apply (base x _mask2Inv)")
		imglib.testOutModes_wrap(_tmpInv, _mask2, msg="Before apply (baseInv x _mask2Inv)")
		
		##[Both inv] BG White but otherwise fine -- Nor, Screen, add(inv), Hard_light, lighten
		#> base x _mask2Inv --> Sub causes White Space where Pink is supposed to be... Mhmm
		
		#if isInBlue:
		#	#_base = _tmpInv
		#	_mask = _mask2
		#	#_mode = blend_modes.dodge
		#	invertFinal = True
		
		
	#:: NORM on WHITE<inv>: Screen, Diff, Add, Nor add correctly, with BLACK of MASK staying BLACK << shouldn't that be WHITE in the end ?
	
	_final = imglib.blend_segmented(_mode, _base, _mask, saturation)
	if __IsTesting:
		_finInv = imglib.invert(_final)
		DisplayWithAspectRatio(opt, 'DEV: Final', _final, 256)
		DisplayWithAspectRatio(opt, 'DEV: FinalInv', _finInv, 256)
		
		imglib.testOutModes_wrap(_final, _mask, msg="After Apply (Final x Mask)")
		imglib.testOutModes_wrap(_finInv, _mask, msg="After Apply (FinalInv x Mask)")
		
		imglib.testOutModes_wrap(_final, _mask2, msg="After Apply (Final x Mask2)")
		imglib.testOutModes_wrap(_finInv, _mask2, msg="After Apply (FinalInv x Mask2)")
		
		
	#imglib.testOutModes_wrap(_mask, _final, msg="After Apply (Mask x Final)")
	## WHITE on WHITE: no changes
	## Red on <WHITE x WHITE>: no changes
	## Red on <WHITE inv>: no changes
	if invertFinal: _final = imglib.invert(_final)
	
	return _final

def handle_Same_R_G_with_B(_color, _bmA, _bmB):
	_bitmask = imglib.blend_segmented(blend_modes.addition, _bmA, _bmB, 1)
	_tmp = np.full(bitmask.shape, 255, dtype="uint8")
	_inverted = imglib.blend_segmented(blend_modes.difference, tmp, bitmask, 1)
	_keeper = imglib.blend_segmented(blend_modes.multiply, image, inverted, 1)
	_final = imglib.getColorImg(opt, maskR, colR_1Red, "All", True)


"""
:: Get Gradient of Color as BlackWhite within the Mask 
there exists cv2.inRange(hsv, lower_limit, upper_limit) ## both as np.array of HSV colors
>	which creates a mask of all pixels that are in range of these two
>	then using bitwise_and of that with the mask to get what you want

print cv2.cvtColor(np.uint8([[[0,255,0 ]]]),cv2.COLOR_BGR2HSV) --> [[[ 60 255 255 ]]] ## Green in BGR to HSV

Able to mix two pictures with np.uint8(img[0] * mask[0] + img[1] * mask[1])

"""
if not isAllSame: ### New tests
	tmpA = None
	tmpB = None
	doBMOnly = False
	dev_invertG = False
	dev_invertB = False
	#print(bwMapArr.keys())
	##### Hair Root
	if flagGreenIsRed:
		maskG = extractChannel(mask, 1).astype("uint8") ## Yellow == Color 2
		bmGreen = applyColor(maskG, colG_2Yellow, "G", dev_invertG, True).astype("uint8")
	elif flagGreen:
		maskG = extractChannel(mask, 1).astype("uint8") ## Yellow == Color 2
		bmGreen = applyColor(maskG, colG_2Yellow, "G", dev_invertG, doBMOnly).astype("uint8")
		tmpA = bmGreen# * maskG
		DisplayWithAspectRatio(opt, "Test2A", tmpA, 256)
		tmpB = tmpA if tmpB is None else tmpB + tmpA
	if tmpB is not None: DisplayWithAspectRatio(opt, "Test2B", tmpB.astype("uint8"), 256)
	##### Hair Tips
	if flagBlueIsRed:
		maskB = extractChannel(mask, 0).astype("uint8") ## Pink   == Color 3
		bmBlue = applyColor(maskB, colB_3Pink, "B", dev_invertB, True).astype("uint8")
	elif flagBlue:
		maskB = extractChannel(mask, 0).astype("uint8") ## Pink   == Color 3
		bmBlue = applyColor(maskB, colB_3Pink, "B", dev_invertB, doBMOnly).astype("uint8")
		tmpA = bmBlue# * maskB
		DisplayWithAspectRatio(opt, "Test3A", tmpA, 256)
		tmpB = tmpA if tmpB is None else tmpB + tmpA
	if tmpB is not None: DisplayWithAspectRatio(opt, "Test3B", tmpB.astype("uint8"), 256)
	##### Main Color
	if flagRed and not (flagIsFullYellow or flagIsFullPink):
		maskR = extractChannel(mask, 2).astype("uint8") ## Red    == Color 1
		bmRed = applyColor(maskR, colR_1Red, "R", False, doBMOnly).astype("uint8")
		#if flagBlue:
		#	DisplayWithAspectRatio(opt, "Test1_R_A", bwMapArr["R"].astype("uint8"), 256)
		#	tmpC = bwMapArr["R"] - bwMapArr["B"]
		#	DisplayWithAspectRatio(opt, "Test1_R_B", tmpC.astype("uint8"), 256)
		tmpA = bmRed#maskR * bmRed
		DisplayWithAspectRatio(opt, "Test1A", tmpA, 256)
		tmpB = tmpA if tmpB is None else tmpB + tmpA
	if tmpB is not None: DisplayWithAspectRatio(opt, "Test1B", tmpB, 256)
	#####
	final = tmpB



## Verified
# If [isAllSame=True], Results look fine if all 3 are same non-BW color with MainTex
if not isAllSame and False:
	##[Verified: With dev_invertG,B = True,False, Hat(WHITE xor WHITE xor RED) works fine]
	# --> R to G == G to R, all three use difference -- R+G and Blue keep BlackArea from Mask, combine to be fine, result a bit darker than before
	##[Verified: With dev_invertG,B = True,False, Pouch(WHITE xor RED xor RED) works ng]
	# --> R to G is Blue areas, G to R is Full White \\ Post-blue is just blue dot
	##[Verified: With dev_invertG,B = True,False ++ always screen, Pouch(WHITE xor WHITE xor RED) works ng]
	##[Verified: With dev_invertG,B = False,False, Hat(WHITE xor WHITE xor RED) is ... ?]
	## Hair: Red:Red = Base, Yellow:Green = Root, Pink:Blue = Tips
	x_Mode     = blend_modes.difference if is_dark else blend_modes.overlay
	if dev_testOff or dev_invertG: x_Mode = blend_modes.difference ## << IMPURITY OF BOTH -- should have been "(NOT X) AND Y"
#	x_ModeBlue = blend_modes.difference if is_dark else blend_modes.hard_light
	if mode is not None: x_Mode = mode
	#final = maskR
	#if dev_testOff:
	#	tmp = np.full(maskR.shape, 255, dtype="uint8")
	#	final = handle_BW(tmp, maskR, "R")
	#	if show: DisplayWithAspectRatio(opt, '[hair] Pre-R', final, 256)
	### Convert to BW, convert into alpha, use that as bitmask for mixing
	if not dev_testOff:
		if not dev_invertG: maskG = imglib.apply_alpha_BW(opt, maskG).astype("uint8")
	
	#imglib.testOutModes_wrap(maskR, maskG)
	## WHITE WHITE RED -- Screen works, Diff not as expected
	
	if colR_1Red == colG_2Yellow:
		_tmpMode = x_Mode
		overwriteMode = True
		x_Mode = blend_modes.normal
		_colArr = invertColorIfApplicable(colR_1Red, "R", dev_invertG)
		tmp = imglib.getColorImg(opt, maskR, _colArr, "R+G", True)
		DisplayWithAspectRatio(opt, '[hair] Pre-XXX', tmp, 256)
		final = handle_BW(tmp, tmp, "G", "R")
		x_Mode = _tmpMode
		overwriteMode = False
	else: final = handle_BW(maskR, maskG, "G", "R")
	if show: DisplayWithAspectRatio(opt, '[hair] Pre-R to G', final, 256)
	#final = handle_BW(maskG, maskR, "R")
	#if show: DisplayWithAspectRatio(opt, '[hair] Pre-G to R', final, 256)
	
	##-- If Mask contains a Pink Layer, apply the hair tip gradient
	if flagBlue:
		isInBlue = True
		if show: DisplayWithAspectRatio(opt, '[hair] Pre-Blue', final, 256)
		if not dev_testOff:
			if not dev_invertB: maskB = imglib.apply_alpha_BW(opt, maskG).astype("uint8") ##<< Given it was a constant, this is never needed anyway
		#else: maskB = imglib.apply_alpha_BW(opt, maskB).astype("uint8")
		if show: DisplayWithAspectRatio(opt, '[hair] Prepare Blue', maskB, 256)
		#imglib.testOutModes_wrap(final, maskB, msg="Prepare Blue")
		### 
		final = handle_BW(final, maskB, "B", "GR" if "GR" in colBW else None)
		## sus
		if show: DisplayWithAspectRatio(opt, '[hair] Post-blue', final, 256)
		##----- Only needed when there is no overlap between the colors... (?)
		if dev_testOff and dev_invertB:
			final = imglib.invert(final).astype("uint8")
			if show: DisplayWithAspectRatio(opt, '[hair] Post-blue2', final, 256)
		##-- Invert again ???
		
elif False:#elif noMainTex:### Works for: [acs_m_accZ4601: German Cross], only two colors
	## Will look ugly on gradient colors
	final = imglib.combineWithBitmask(opt, maskR, maskG, getBMbyTag("G"))
	if flagBlue:
		if show: DisplayWithAspectRatio(opt, '[NT] Pre-Blue', final, 256)
		final = imglib.combineWithBitmask(opt, final, maskB, getBMbyTag("B"))

### If no MainTex exists, use the ColorMask directly
if (noMainTex):
	DisplayWithAspectRatio(opt, '[I] Final no Main', final.astype("uint8"), 256)
	image = final
else: ### Otherwise apply the ColorMask to it (a fully white ColorMask will have zero effect)
	if show: DisplayWithAspectRatio(opt, '[I] Pre-merge', image, 256)
	image = imglib.blend_segmented(blend_modes.multiply, image, final, 1)

#### Remerge Alpha & add unaffected areas (solid black in ColorMask) back
# Note: For fizzling Gradients to work, use an extra free layer I guess <<see Finana Honkai>>
if has_alpha:
	keeper = keeper.astype(float)
	DisplayWithAspectRatio(opt, 'Pre-alpha', image.astype("uint8"), 256)
	image = cv2.merge([image[:,:,0], image[:,:,1], image[:,:,2], imgAlpha.astype(float)])
	keeper = cv2.merge([keeper[:,:,0], keeper[:,:,1], keeper[:,:,2], imgAlpha.astype(float)])
	image = imglib.combineWithBitmask(opt, image, keeper, inverted)
elif not isAllSame and False:
	## smt a bit fuzzy here -- Repair that later
	image = imglib.combineWithBitmask(opt, image.astype("uint8"), keeper, inverted)

#DisplayWithAspectRatio(opt, 'Final_float', image, 256) ## OK
#DisplayWithAspectRatio(opt, 'Final_uint8', image.astype("uint8"), 256) ## Ok
#image1 = imglib.combineWithBitmask(opt, image.astype("uint8"), keeper, inverted)
#DisplayWithAspectRatio(opt, 'Final_image+Keeper1', image1, 256) ## Ok
#image1 = imglib.combineWithBitmask(opt, image.astype("uint8"), keeper.astype("uint8"), inverted)
#DisplayWithAspectRatio(opt, 'Final_image+Keeper2', image1, 256) ## Ok
#image1 = imglib.combineWithBitmask(opt, image, keeper, inverted)
#DisplayWithAspectRatio(opt, 'Final_image+Keeper3', image1, 256) ## Black
#image1 = imglib.combineWithBitmask(opt, image, keeper.astype("uint8"), inverted)
#DisplayWithAspectRatio(opt, 'Final_image+Keeper4', image1, 256) ## Black



DisplayWithAspectRatio(opt, 'Final', image.astype("uint8"), 256)
if show: k = cv2.waitKey(0) & 0xFF
cv2.destroyAllWindows()

## Short remark: If certain parts appear purple in [G]-Pictures but end up being "Green"
## Then the reason for this is that there was simply no [B] to handle the "Blue" part.
##### The "purple" might even be an error, as it only appears with float, but not with int
## The image written to disk will contain the 'purple', through.

### Write out final image
outName = imgMain[:-4] + "_pyCol.png"
if noMainTex: outName = imgMask[:-4] + "_pyCol.png"
if altName is not None: outName = os.path.join(os.path.split(outName)[0], altName + "_pyCol.png")
cv2.imwrite(outName, image)
print("Wrote output image at\n" + outName)
