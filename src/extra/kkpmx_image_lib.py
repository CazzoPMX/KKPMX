# Cazoo - 2021-05-20
# This code is free to use and re-distribute, but I cannot be held responsible for damages that it may or may not cause.
#####################
import sys
import cv2
import numpy as np
import blend_modes


def makeOptions(_opt):
	return {
		"alpha": _opt.get("alpha", 64 / 255),
		"show":  _opt.get("show", False),
		"mode":  _opt.get("mode", "Additive"),
		"scale": _opt.get("scale", 1),
	}

######
## Display
######

def printImageStats(img):
	print(type(img))
	print("shape={}, dtype={}".format(img.shape, img.dtype))

#### https://stackoverflow.com/questions/35180764/opencv-python-image-too-big-to-display
#> rewrote to be "cv2.show" instead of return
def DisplayWithAspectRatio_f(opt, title, _img, width=None, height=None, inter=cv2.INTER_AREA):
	if not opt["show"]: return
	if opt["scale"] == 1: img = _img#.astype("uint8")
	else:                 img = (_img * opt["scale"])#.astype("uint8")
	DisplayWithAspectRatio(opt, title, img, width, height, inter)

def DisplayWithAspectRatio(opt, title, _img, width=None, height=None, inter=cv2.INTER_AREA):
	if not opt["show"]: return
	img = _img.astype("uint8")
	dim = None
	(h, w) = img.shape[:2]

	if width is None and height is None:
		return
	if width is None:
		r = height / float(h)
		dim = (int(w * r), height)
	else:
		r = width / float(w)
		dim = (width, int(h * r))

	cv2.imshow(title, cv2.resize(img, dim, interpolation=inter))

######
## Helpers
######

def converter255(img, imgAlpha=None): ## read: [imgAlpha, cv2]
	if img.shape[2] == 4:
		#return (cv2.merge([img[:,:,0], img[:,:,1], img[:,:,2], img[:,:,3]]) / 255).astype(float)
		return img.astype(float)
	if imgAlpha is not None:
		return (cv2.merge([img[:,:,0], img[:,:,1], img[:,:,2], imgAlpha])).astype(float)
	#return (cv2.merge([img[:,:,0], img[:,:,1], img[:,:,2]]) / 255).astype(float)
	return img.astype(float)

def converterX(img, imgAlpha=None): ## read: [imgAlpha, cv2]
	if img.shape[2] == 4:
		#return (cv2.merge([img[:,:,0], img[:,:,1], img[:,:,2], img[:,:,3]]) / 255).astype(float)
		return (img / 255).astype(float)
	if imgAlpha is not None:
		return (cv2.merge([img[:,:,0], img[:,:,1], img[:,:,2], imgAlpha]) / 255).astype(float)
	#return (cv2.merge([img[:,:,0], img[:,:,1], img[:,:,2]]) / 255).astype(float)
	return (img / 255).astype(float)

def converterScaled(opt, img, imgAlpha=None, addAlpha=False): ## read: [imgAlpha, cv2]
	if img.shape[2] == 4:
		return (img / opt["scale"]).astype(float)
	if addAlpha and imgAlpha is None:
		imgAlpha = np.ones(img.shape[:2], dtype='uint8') * 255
	if imgAlpha is not None:
		return (cv2.merge([img[:,:,0], img[:,:,1], img[:,:,2], imgAlpha]) / opt["scale"]).astype(float)
	return (img / opt["scale"]).astype(float)
def converter(img, imgAlpha=None, addAlpha=False): return converterScaled({ "scale": 1}, img, imgAlpha, addAlpha)

def resize(imgSource, imgTarget):
    if type(imgTarget) in [list,tuple]: shape = imgTarget
    else:                               shape = imgTarget.shape

    if (imgSource.shape[:2] != shape[:2]):
        target = shape
        source = imgSource.shape
        width  = int(source[1] * (target[1] / source[1]))
        height = int(source[0] * (target[0] / source[0]))
        #print("{} * ({} / {} = {}) == {}".format(source[1], target[1], source[1], target[1] / source[1], width))
        #print("{} * ({} / {} = {}) == {}".format(source[0], target[0], source[0], target[0] / source[0], height))
        return cv2.resize(imgSource, (width, height), interpolation=cv2.INTER_NEAREST)
    return imgSource

def normalize_color(color): ## from: body_overtex1
	if any([x > 1 for x in color]):
		if len(color) == 3: color.append(255)
		return color
	if len(color) == 3: color.append(1)
	return [ int(color[0]*255), int(color[1]*255), int(color[2]*255), int(color[3]*255) ]

def extendChannel(img, _alpha=None):
	if _alpha is None: _alpha = np.ones(img.shape[:2], dtype="uint8") * 255
	return cv2.merge([img, img, img, _alpha])

def extendAlpha(img):
	tmp = np.ones(img.shape[:2], dtype="uint8") * 255
	return cv2.merge([tmp, tmp, tmp, img])

def resizeWithAspectRatio(_img, width=None, height=None):
	dim = None
	img = _img.astype("uint8")
	(h, w) = img.shape[:2]

	if width is None and height is None:
		return
	if width is None:
		r = height / float(h)
		dim = (int(w * r), height)
	else:
		r = width / float(w)
		dim = (width, int(h * r))
	return resize(_img, dim)

def get_blend_mode(blend_mode):
	blendDict = {#		mode = "darken" ## Try: "mul" "diff" "nor"
		"normal": blend_modes.normal,
		"overlay": blend_modes.overlay,
		"add": blend_modes.addition,
		"darken": blend_modes.darken_only,
		"mul": blend_modes.multiply,
		"diff": blend_modes.difference,
	}
	if blend_mode not in blendDict: raise Exception("Unknown blend_mode " + blend_mode)
	return blendDict[blend_mode]

def blend_segmented(blend_mode, main, mask, alpha):
	if type(blend_mode) == str: blend_mode = get_blend_mode(blend_mode)
	_main = converter(main, addAlpha=True)
	_mask = converter(mask, addAlpha=True)
	def buildRange(axis, size):
		ret = []
		arr = [x for x in range(0, axis, size)]
		while len(arr) > 1:
			val = arr.pop(0)
			ret.append(slice(val, arr[0]))
		## we want the end + last is always omitted
		ret.append(slice(arr[0], axis))
		return ret
	height = buildRange(_main.shape[0], 1024)
	width = buildRange(_main.shape[1], 1024)
	image = np.zeros(_main.shape, dtype='float')
	for y in height:
		for x in width:
			image[y,x,:] = blend_mode(_main[y,x,:], _mask[y,x,:], alpha)
	return image

######
## Main
######

def applyColor(opt, _mask, _colArr, tag): ## read: [show, np, cv2, mode, alpha, beta], write: [bitmaskArr]
	"""
	_mask :: One Color channel of [imgMask] as BW, extended into 3-Channel
	:: Only cv2.show & cv2.addWeighted need it as 3-Channel + Convenient for 'Additive'
	_colArr :: An [ R, G, B ] Array; Alpha is discarded
	
	Given a mask [0], apply an RGB color [1] where '[0].pixel > 0'
	"""
	if opt["show"]: print(_colArr)
	if len(_colArr) == 3: _colArr.push(1)

	## Make a white image to create a mask for "above 0"
	bitmask = np.ones(_mask.shape[:2], dtype="uint8") * 255
	bitmask[:,:] = (_mask[:,:,3] != 0)
	#if len(_colArr) == 4:
	#	bitmask = cv2.merge([bitmask*255, bitmask*255, bitmask*255, bitmask*255])
	#else:
	
	#print(bitmask.dtype)
	#print(_mask.dtype)
	bitmaskCol = cv2.merge([bitmask*255, bitmask*255, bitmask*255, bitmask*255])
	bitmaskNon = cv2.merge([(1-bitmask)*255, (1-bitmask)*255, (1-bitmask)*255, (1-bitmask)*255])
	
	bitmask = bitmaskCol
	# (_mask[:,:,3]*255).astype("uint8")
	DisplayWithAspectRatio(opt, 'bitmask'+tag, bitmask.astype("uint8"), 256) ## Where to add color
	#bitmaskArr.append(bitmask)
	
	#print("{},{},{}".format(type(bitmaskNon),bitmaskNon.shape, bitmaskNon.dtype))
	#print("{},{},{}".format(type(_mask),_mask.shape, _mask.dtype))
	mask_rest  = np.bitwise_and(bitmaskNon, _mask.astype("uint8"))
	
	## Create an image of this color
	colImg0 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[0]
	colImg1 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[1]
	colImg2 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[2]
	colImg3 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[3]
	#if _mask.shape[2] == 4: 
	#	colImg3 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[3]
	#	colImg = cv2.merge([colImg2, colImg1, colImg0, colImg3]) ## Apparently the KK-RGB is as BGR ???
	#	#colImg = cv2.merge([colImg0, colImg1, colImg2, colImg3]) ## Apparently the KK-RGB is as BGR ???
	#else:
	colImg = cv2.merge([colImg2, colImg1, colImg0, colImg3]) ## Apparently the KK-RGB is as BGR ???
	DisplayWithAspectRatio(opt, 'Color'+tag,     colImg.astype("uint8"), 256)## A canvas of this Color
	DisplayWithAspectRatio(opt, 'ColorMask'+tag, _mask.astype("uint8"), 256)## How the channel looks
	
	## Apply that color
	_maskA = None
	#if _mask.shape[2] == 4: _maskA = _mask[:,:,3]# * (_colArr[3]/255)
	#testOutModes(opt, converter(opt, colImg), converter(opt, _mask), 256, True)
	if opt["mode"] == "Overlay":
		#_mask = cv2.addWeighted(_mask, 1 - opt["alpha"], colImg, opt["alpha"], 0)
		#_mask = cv2.addWeighted(_mask, 1 - opt["alpha"], colImg, opt["alpha"], 0)
		_mask = cv2.addWeighted(_mask[:,:,:], 1 - opt["alpha"], colImg, opt["alpha"], 0)
	elif opt["mode"] == "Diff":
		_mask = blend_modes.difference(converter(opt, colImg), converter(opt, _mask), opt["alpha"]) * 255

	elif opt["mode"] == "Additive":
		_mask[:,:,0] = ((_mask[:,:,0] / 255) * (colImg[:,:,0]))
		_mask[:,:,1] = ((_mask[:,:,1] / 255) * (colImg[:,:,1]))
		_mask[:,:,2] = ((_mask[:,:,2] / 255) * (colImg[:,:,2]))
		#_mask[:,:,3] = ((_mask[:,:,3] / 255) * (colImg[:,:,3]))
		#testOutModes(opt, converter(opt, colImg), converter(opt, _mask), 256)
		#_mask = blend_modes.addition(converter(opt, colImg), converter(opt, _mask), opt["alpha"]) * 255
	if opt["show"]: cv2.imshow('Unmasked + Color:'+tag, _mask)
	
	#if _maskA is not None:
	#	_mask = cv2.merge([_mask[:,:,0], _mask[:,:,1], _mask[:,:,2], _maskA])
	
	_mask = _mask.astype("uint8")
	
	## Apply mask again
	#print("{},{},{}".format(type(bitmask),bitmask.shape, bitmask.dtype))
	#print("{},{},{}".format(type(_mask),_mask.shape, _mask.dtype))
	mask_color = np.bitwise_and(bitmask, _mask)
	
	return blend_modes.addition(converter(opt, mask_color), converter(opt, mask_rest), 1) * 255

def applyColor_org(opt, _mask, _colArr, tag): ## Original from [ColorMask]
	"""
	_mask :: One Color channel of [imgMask] as BW, extended into 3-Channel
	:: Only cv2.show & cv2.addWeighted need it as 3-Channel + Convenient for 'Additive'
	_colArr :: An [ R, G, B ] Array; Alpha is discarded
	
	Given a mask [0], apply an RGB color [1] where '[0].pixel > 0'
	"""
	if opt["show"]: print(_colArr)
	#tag = str(_colArr[0])
	## Make a white image to create a mask for "above 0"
	bitmask = np.ones(_mask.shape[:2], dtype="uint8") * 255
	bitmask[:,:] = (_mask[:,:,0] != 0)
	#if len(_colArr) == 4:
	#	bitmask = cv2.merge([bitmask*255, bitmask*255, bitmask*255, bitmask*255])
	#else:
	bitmask = cv2.merge([bitmask*255, bitmask*255, bitmask*255])
	if opt["show"]: cv2.imshow('bitmask'+tag, bitmask) ## Where to add color
	#bitmaskArr.append(bitmask)
	
	## Create an image of this color
	colImg0 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[0]
	colImg1 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[1]
	colImg2 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[2]
	#if _mask.shape[2] == 4: 
	#	colImg3 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[3]
	#	colImg = cv2.merge([colImg2, colImg1, colImg0, colImg3]) ## Apparently the KK-RGB is as BGR ???
	#	#colImg = cv2.merge([colImg0, colImg1, colImg2, colImg3]) ## Apparently the KK-RGB is as BGR ???
	#else:
	colImg = cv2.merge([colImg2, colImg1, colImg0]) ## Apparently the KK-RGB is as BGR ???
	if opt["show"]: cv2.imshow('Color'+tag, colImg)  ## A canvas of this Color
	if opt["show"]: cv2.imshow('ColorMask'+tag, _mask) ## How the channel looks
	
	## Apply that color
	_maskA = None
	#if _mask.shape[2] == 4: _maskA = _mask[:,:,3]# * (_colArr[3]/255)
	if opt["mode"] == "Overlay":
		#_mask = cv2.addWeighted(_mask, 1 - opt["alpha"], colImg, opt["alpha"], 0)
		#_mask = cv2.addWeighted(_mask, 1 - opt["alpha"], colImg, opt["alpha"], 0)
		_mask = cv2.addWeighted(_mask[:,:,:3], 1 - opt["alpha"], colImg, opt["alpha"], 0)
	elif opt["mode"] == "Additive":
		#print(_colArr[0], " -> ", _colArr[0] / 255)
		#print((_mask[0,0,:]))
		#print((_mask[0,0,:] / 255))
		#print((_mask[0,0,:] / 255) * _colArr)
		#print((_mask[0,0,:]) * (_colArr / 255))
		
		_mask[:,:,0] = ((_mask[:,:,0] / 255) * (colImg[:,:,0]))
		_mask[:,:,1] = ((_mask[:,:,1] / 255) * (colImg[:,:,1]))
		_mask[:,:,2] = ((_mask[:,:,2] / 255) * (colImg[:,:,2]))
		#testOutModes(opt, converter(opt, colImg), converter(opt, _mask), 256)
		#_mask = blend_modes.addition(converter(opt, colImg), converter(opt, _mask), opt["alpha"]) * 255
	if opt["show"]: cv2.imshow('Unmasked + Color:'+tag, _mask)
	
	#if _maskA is not None:
	#	_mask = cv2.merge([_mask[:,:,0], _mask[:,:,1], _mask[:,:,2], _maskA])
	
	_mask = _mask.astype("uint8")
	
	## Apply mask again
	return np.bitwise_and(bitmask, _mask)

def getColorMask(opt, _mask, _colArr, tag): ## from [overtex]
	"""
	_mask :: One Color channel of [imgMask] as BW, extended into 3-Channel
	:: Only cv2.show & cv2.addWeighted need it as 3-Channel + Convenient for 'Additive'
	_colArr :: An [ R, G, B ] Array; Alpha is discarded
	
	Given a mask [0], create a colImg based on an RGBA color [1] that is affected by [0].alpha
	"""
	if opt["show"]: print(_colArr)
	if len(_colArr) == 3: _colArr.push(1)
	
	## Create an image of this color
	colImg0 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[0]
	colImg1 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[1]
	colImg2 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[2]
	colImg3 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[3]
	
	colImg = cv2.merge([colImg2, colImg1, colImg0, colImg3]) ## Apparently the KK-RGB is as BGR, so do that
	#DisplayWithAspectRatio(opt, 'Color'+tag,     colImg.astype("uint8"), 256)## A canvas of this Color

	mask_color = np.bitwise_and(extendAlpha(_mask[:,:,3]), colImg)

	DisplayWithAspectRatio(opt, 'ColorMaskAlpha'+tag, mask_color, 256)## A canvas of this Color
	return mask_color

######
## Small
######

def convert_to_BW(image):
	convCh = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
	return cv2.merge([convCh, convCh, convCh, image[:,:,3]])

def invert_f(image):
	return cv2.merge([1 - imgBase_f[:,:,0], 1 - imgBase_f[:,:,1], 1 - imgBase_f[:,:,2], imgBase_f[:,:,3]])

######
## Tester
######
def testOutModes_wrap(main, mask): ## To use [testOutModes] in ad-hoc way
	show = True
	opt = makeOptions(locals())
	_main = converterScaled(opt, main, None, True)
	_mask = converterScaled(opt, mask, None, True)
	testOutModes(opt, _main, _mask, 256, "<< Using Wrapper >>", advanced=True)

"""
#### https://pythonhosted.org/blend_modes/
#### %appdata%\..\Local\Programs\Python\Python38-32\Lib\site-packages\blend_modes
a = base \\ b = top layer \\ ai,bi = inverted

BW image == homogenous grayscale
_ab := If one is BW and other not, the non BW one
_AB := If one is BW and other not, the BW one

Normal        ([01] bm.normal)			== b // == alpha(b,a)
#// Multiply and Screen
Multiply      ([08] bm.multiply)		== a * b
>	if either is BW, equivalent to normal("black", _ab, alpha=_AB)
Screen        ([04] bm.screen)			== 1 - ai * bi
>	if either is BW, equivalent to normal(_ab, "white", alpha=_AB)
Overlay       ([15] bm.overlay)			== (a < 0.5) ? 2 a b : 1 - 2 ai bi
>	B << A => Lighten, B >> A -> Darken
>	Linear interpolation between black \\ [B] \\ white (at a=0, 0.5, 1)
Hard Light    ([09] bm.hard_light)		== overlay(b, a, alpha)
Soft Light    ([02] bm.soft_light)		== IMG_RGB_iv * multiply + IMG_RGB * screen
>	Softer version (more base bleeding)
#// Dodge and Burn
Dodge         ([05] bm.dodge)			== np.min(IMG_RGB / TAR_RGB_iv, 1)
Burn          							== Dodge of negative; darkens
#// Simple arithmetic
Divide        ([14] bm.divide)			== (256 / 255 * IMG_RGB) / (1 / 255 + TAR_RGB)
Addition      ([06] bm.addition)		== IMG_RGB + TAR_RGB
Subtract      ([11] bm.subtract)		== IMG_RGB - TAR_RGB
Difference    ([10] bm.difference)		== IMG_RGB - TAR_RGB; OUT[OUT < 0] *= -1
>	No change with black, inverted with White
Darken Only   ([07] bm.darken_only)		== np.min(IMG_RGB, TAR_RGB)
Lighten Only  ([03] bm.lighten_only)	== np.max(IMG_RGB, TAR_RGB)
#// Other
Grain Extract ([12] bm.grain_extract, GIMP) == np.clip(IMG_RGB - TAR_RGB + 0.5, 0, 1)
Grain Merge   ([13] bm.grain_merge, GIMP)   == np.clip(IMG_RGB + TAR_RGB + 0.5, 0, 1)
"""
def testOutModes(opt, _imgA, _imgB, size, msg="", advanced=False, _alpha=None):
	if not opt["show"]: return
	print("ColorTest: " + msg)
	alpha = opt["alpha"] if _alpha is None else _alpha
	scale = opt["scale"]
	imgA = _imgA.astype(float)
	imgB = _imgB.astype(float)
	
	img_seg = blend_modes.normal(imgA, imgB, alpha) * scale
	DisplayWithAspectRatio(opt, '[Nor]', img_seg, size) ### Alpha only
	img_seg = blend_modes.overlay(imgA, imgB, alpha) * scale
	DisplayWithAspectRatio(opt, '[Ovl]', img_seg, size) ### Alpha only
	img_seg = blend_modes.multiply(imgA, imgB, alpha) * scale
	DisplayWithAspectRatio(opt, '[Mul]', img_seg, size) ### Alpha only
	img_seg = blend_modes.difference(imgA, imgB, alpha) * scale
	DisplayWithAspectRatio(opt, '[Diff]', img_seg, size) ### Inverted + alpha: Alpha
	if advanced:
		img_seg = blend_modes.addition(imgA, imgB, alpha) * scale
		DisplayWithAspectRatio(opt, '[Add]', img_seg, size) ## Inverted color without Alpha
		img_seg = blend_modes.subtract(imgA, imgB, alpha) * scale
		DisplayWithAspectRatio(opt, '[Sub]', img_seg, size) ## Scambled, without Alpha
		img_seg = blend_modes.soft_light(imgA, imgB, alpha) * scale
		DisplayWithAspectRatio(opt, '[Soft Light]', img_seg, size) ### Alpha only
		img_seg = blend_modes.lighten_only(imgA, imgB, alpha) * scale
		DisplayWithAspectRatio(opt, '[Lighten]', img_seg, size) ### Increase LUM of A by alpha*B
		img_seg = blend_modes.darken_only(imgA, imgB, alpha) * scale ### Normal + alpha; Better [White] than inv+Difference
		DisplayWithAspectRatio(opt, '[Darken]', img_seg, size)
		img_seg = blend_modes.hard_light(imgA, imgB, alpha) * scale
		DisplayWithAspectRatio(opt, '[Hard_Light]', img_seg, size) ### Alpha only
		img_seg = blend_modes.dodge(imgA, imgB, alpha) * scale
		DisplayWithAspectRatio(opt, '[Dodge]', img_seg, size) ### No effect
		img_seg = blend_modes.screen(imgA, imgB, alpha) * scale
		DisplayWithAspectRatio(opt, '[Screen]', img_seg, size) ### == Add
		img_seg = blend_modes.divide(imgA, imgB, alpha) * scale
		DisplayWithAspectRatio(opt, '[Div]', img_seg, size) ### Scambled
		img_seg = blend_modes.grain_extract(imgA, imgB, alpha) * scale
		DisplayWithAspectRatio(opt, '[GExtract]', img_seg, size) ### Scambled
		img_seg = blend_modes.grain_merge(imgA, imgB, alpha) * scale
		DisplayWithAspectRatio(opt, '[GMerge]', img_seg, size) ### Alpha only
	k = cv2.waitKey(0) & 0xFF

