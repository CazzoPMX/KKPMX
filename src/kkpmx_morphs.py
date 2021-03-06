# Cazoo - 2022-05-13
# This code is free to use and re-distribute, but I cannot be held responsible for damages that it may or may not cause.
#####################
from typing import List, Union, Tuple
import re, os, json, copy  ## copy.deepcopy

import kkpmx_core as kklib
import kkpmx_utils as util
from kkpmx_utils import find_bone, find_mat, find_disp, find_morph, find_rigid, __typePrinter

try:
	import nuthouse01_core as core
	import nuthouse01_pmx_parser as pmxlib
	import nuthouse01_pmx_struct as pmxstruct
	import _prune_unused_bones as bonelib
	import _translation_tools as tlTools
	import morph_scale
except ImportError as eee:
	print(eee.__class__.__name__, eee)
	print("ERROR: failed to import some of the necessary files, all my scripts must be together in the same folder!")
	print("...press ENTER to exit...")
	input()
	exit()
	core = pmxlib = pmxstruct = morph_scale = bonelib = None


## Local "moreinfo"
DEBUG = util.DEBUG or False
state = {}

#--- [Text]: How it appears in the exported morph name
#--- [Morph]: The name how it should be displayed in MMD [== name_en]
#--- [KK Name]: The Display name in the respective dropdown in KK
#--- [EN]: The segment for the VertexMorph (maybe only JP / EN ?)
#--- [JP]: "name_jp" of the morph. Should reflect the phrase most commonly used in dance motions.
prefixes = [ # ["Text", "", "", "EN"]
	## Combos for convenience
	["eye", "", "", "eye"],
	["kuti", "", "", "mouth|teeth|canine|tongue"],
	["mayuge", "", "", "eyebrow"],
	####
	["eye_face"   , "", "", "eyes"],
	["kuti_face"  , "", "", "mouth"],
	["eye_nose"   , "", "", "eye.nose"],
	["kuti_nose"  , "", "", "mouth.nose"],
	["eye_siroL"  , "", "", "eye.siroL"],
	["eye_siroR"  , "", "", "eye.siroR"],
	["eye_line_u" , "", "", "eyeline_u"],
	["eye_line_l" , "", "", "eyeline_l"],
#	["eye_naL"    , "", "", ""],
#	["eye_naM"    , "", "", ""],
#	["eye_naS"    , "", "", ""],
	["kuti_ha"    , "", "", "teeth"],
	["kuti_yaeba" , "", "", "canine"],
	["kuti_sita"  , "", "", "tongue"],
	["mayuge"     , "", "", "brow"],
	]
infixes  = [ # ["Text", "Morph", "KK Name", ".EN", "JP", ]
	["_a"         , "Say 'A'"      ,  ".." , ".a", "???"],
	["_e"         , "Say 'E'"      ,  ".." , ".e", "???"],
	["_i"         , "Say 'I'"      ,  ".." , ".i", "???"],
	["_o"         , "Say 'O'"      ,  ".." , ".o", "???"],
	["_u"         , "Say 'U'"      ,  ".." , ".u", "???"],
	["_n"         , "Say 'N'"      ,  ".." , ".n", "???"],
	## Mayuge only[B]
	##### Both[X]
	##### Eye or Mayuge only[E]
	##### Mouth only[M]
	["_akire"     , "Flustered"    ,  "Flustered"   , ".zzz", ""   ],#[M] ?????????		Haste
	["_aseri"     , ""             ,  ""            , ".zzz", ""   ],#[X] ?????????		Haste
	["_bisyou"    , "Grin"         ,  "Grin"        , ".zzz", ""   ],#[X] ????????????		Smile
	["_def"       , "default"      ,  "default"     , ".default", "" ],#[X] ???????????????	
	["_doki"      , ""             ,  ""            , ".zzz", ""   ],#[M] ??????		
	["_doya"      , "Smug"         ,  "Smug"        , ".zzz", ""   ],#[X] ??????		
	["_egao"      , "Smiling"      ,  "Smiling"     , ".smile", ""   ],#[X] ?????????		
	["_gag"       , ""             ,  ""            , ".zzz", ""   ],#[E] ??????		
	["_gyu"       , ""             ,  ""            , ".zzz", ""   ],#[E] ??????		
	["_gyul"      , ""             ,  ""            , ".zzz", ""   ],#[E] 			
	["_gyur"      , ""             ,  ""            , ".zzz", ""   ],#[E] 			
	["_huan"      , ""             ,  ""            , ".zzz", ""   ],#[B] 			
	["_human"     , "Pouting"      ,  "Grumbling"   , ".zzz", ""   ],#[M] ?????????		
	["_ikari"     , "Angry"        ,  "Angry"       , ".zzz", ""   ],#[X] ?????????		
	["_kanasi"    , "Sad 2"        ,  "Sad 2"       , ".zzz", ""   ],#[E] ?????????		
	["_keno"      , "Disgust"      ,  "Disgust"     , ".zzz", "??????"   ],#[X] ??????		
	["_kisu"      , "Kiss"         ,  "Kiss"        , ".zzz", ""   ],#[M] ??????		
	["_koma"      , ""             ,  ""            , ".zzz", ""   ],#[B] ??????		
	["_komaru"    , "Concerned"    ,  "Concerned"   , ".zzz", ""   ],#[E] ?????????		
	["_kurusi"    , "In Pain"      ,  "In Pain"     , ".zzz", ""   ],#[E] ?????????		
	["_kuwae"     , "Sucking"      ,  "Sucking"     , ".zzz", ""   ],#[M] ?????????		
	["_mogu"      , ""             ,  ""            , ".zzz", ""   ],#[M]
	["_naki"      , "Crying"       ,  "Crying"      , ".zzz", ""   ],#[E] ??????		
	["_name"      , "Licking"      ,  "Licking"     , ".zzz", ""   ],#[M] ??????		
	["_neko"      , ""             ,  ""            , ".zzz", ""   ],#[M]
	["_niko"      , ""             ,  ""            , ".zzz", ""   ],#[M]
	["_odoro"     , "Surprised"    ,  "Surprised"   , ".zzz", ""   ],#[X] ?????????		
	["_oko"       , "Angry"        ,  ""            , ".zzz", ""   ],#[B] 			
	["_pero"      , "Bleh"         ,  "Bleh"        , ".zzz", ""   ],#[M] ??????		
	["_rakutan"   , "Upset"        ,  "Upset"       , ".zzz", ""   ],#[E] ????????????	
	["_sabisi"    , "Lonely"       ,  "Lonely"      , ".zzz", ""   ],#[M] ?????????		
	["_san"       , ""             ,  ""            , ".zzz", ""   ],#[M]
	["_setunai"   , "Sad"          ,  "Sad"         , ".zzz", ""   ],#[E] ????????????	
	["_sian"      , "Thoughtful"   ,  "Thoughtful"  , ".zzz", ""   ],#[E] ?????????		
	["_sinken"    , "Serious"      ,  "Serious"     , ".zzz", ""   ],#[X] ????????????	
	["_tabe"      , ""             ,  ""            , ".zzz", ""   ],#[M]
	["_tere"      , "Shy"          ,  "Shy"         , ".zzz", ""   ],#[E] ??????		
	["_tmara"     , ""             ,  ""            , ".zzz", ""   ],#[B] 			
	["_tumara"    , "Bored"        ,  "Bored"       , ".zzz", ""   ],#[E] ?????????		
	["_uresi"     , "Happy"        ,  "Happy"       , ".zzz", ""   ],#[M] ?????????		
	["_winkl"     , "Wink L"       ,  "Wink L"      , ".zzz", ""   ],#[E] ????????????		
	["_winkr"     , "Wink R"       ,  "Wink R"      , ".zzz", ""   ],#[E] 			
#	["_doki_s"    , ""             ,  ""            , ".zzz", ""   ],#[X] 			
#	["_doki_ss"   , ""             ,  ""            , ".zzz", ""   ],#[X] 			
#	["_gyu02"     , ""             ,  ""            , ".zzz", ""   ],#[E] 			
#	["_gyul02"    , ""             ,  ""            , ".zzz", ""   ],#[E] 			
#	["_ikari02"   , ""             ,  ""            , ".zzz", ""   ],#[X] 			
#	["_name02"    , ""             ,  ""            , ".zzz", ""   ],#[M] 			
#	["_odoro_s"   , ""             ,  ""            , ".zzz", ""   ],#[X] 			
#	["_sianL"     , ""             ,  ""            , ".zzz", ""   ],#[B] 			
#	["_sianR"     , ""             ,  ""            , ".zzz", ""   ],#[B] 			
#	["_sinken02"  , ""             ,  ""            , ".zzz", ""   ],#[X] 			
#	["_sinken03"  , ""             ,  ""            , ".zzz", ""   ],#[X] 			
#	["_uresi_s"   , "Happy"        ,  "Happy"       , ".zzz", ""   ],#[M] 			
#	["_uresi_ss"  , "Happy"        ,  "Happy"       , ".zzz", ""   ],#[M] 			
	]
suffixes = [ # ["Text", "Morph", "", "EN"]
	["_op" , ""            , "", ".open"],
	["_cl" , " (closed)"   , "", ".close"],
	["_s"  , " (small)"    , "", ".s"],
	["_ss" , " (small 2)"  , "", ".s2"],
	["_l"   , " (big)"     , "", ".l"],
	["02"  , " 2"          , "", ".2"],
	["03"  , " 3"          , "", ".3"],
#	["l"   , " (Left)"     , "", ".left"],
#	["r"   , " (Right)"    , "", ".right"],
#	[""    , ""],
	]
########
def genGroupItem(pmx, arr): ## only existing morphs are added
	lst = [find_morph(pmx, elem[0], False) for elem in arr]
	return [pmxstruct.PmxMorphItemGroup(lst[idx], elem[1]) for (idx,elem) in enumerate(arr) if lst[idx] != -1]
def replaceItems(pmx, name, arr): ## Does nothing if [name] is not found
	morph = find_morph(pmx, name, False)
	if morph != -1: pmx.morphs[morph].items = genGroupItem(pmx, arr)
def translateItem(name): ## Always input the untranslated name
	parts = re.search("(\w+)\.[a-z]+\d+(_[a-z]+)(\w+)", name) ## \2\t\1 \3
	if not parts: return name
	if len(parts.groups()) != 4: return name
	dest = ""
	## Get Prefix
	m = parts.group(1)
	arr = [x[3] for x in prefixes if x[0] == m]
	dest += arr[0] if len(arr) > 0 else m
	## Get Infix
	m = parts.group(2)
	arr = [x[3] for x in infixes if x[0] == m]
	dest += arr[0] if len(arr) > 0 else m
	## Get Suffix
	m = parts.group(3)
	arr = [x[3] for x in suffixes if x[0] == m]
	dest += arr[0] if len(arr) > 0 else m
	if dest == parts.group(1) + parts.group(2) + parts.group(3): return name
	if len(dest) == 0: return name
	return dest

## Create or find a given morph and write the given fields
def addOrReplace(pmx, name_jp, name_en, panel, items:List[Tuple[str, float]]):# > PMX, "", "", int, [ ("", 0.0) ]
	""" IN: PMX, str, str, int, List<Tuple<str, float>> ==> OUT: void """
	# if exist: get from store & set Idx \\ else: create new, append, set Idx
	idx = find_morph(pmx, name_jp, False)
	if idx == -1:
		idx = len(pmx.morphs)
		pmx.morphs.append(pmxstruct.PmxMorph(name_jp, "", 0, 0, []))
	morph = pmx.morphs[idx]
	morph.name_en = name_en
	morph.panel   = panel
	morph.items   = genGroupItem(pmx, items)

## Returns the name by which this morph can be found, or ""
def find_one_morph(_morphs, name, value=None) -> Union[str, Tuple[str, float]]:
	"""
	IN: List[str], str, float=None
	OUT(value=None): str
	OUT(value=float): Tuple[str, float]
	
	OUT.str may be "" if IN.name is not a Morph
	"""
	ret = ["", value]
	dest = translateItem(name)
	if name in _morphs: ret[0] = name
	elif dest in _morphs: ret[0] = dest
	if value is None: return ret[0]
	return tuple(ret)

####
### Remark: Throw out all of the "translated" matches again
def find_all_morphs(_morphs, prefix=None, infix=None, suffix=None, value=None, isVocal=False) -> Union[List[str], List[Tuple[str, float]]]:
	"""
	OUT(empty):       []
	OUT(value==None): List[str]
	OUT(value!=None): List[Tuple[str, float]]
	"""
	verbose = state.get("moreinfo", True)
	## Get all morphs
	morphs = copy.copy(_morphs)
	if verbose: print(f"\nFind all morphs called <{prefix}:{infix}:{suffix}>")
	## Reduce by prefixes, if any
	if prefix is not None: ## Only match at start
		pat = [x[3] for x in prefixes if x[0] == prefix]
		if len(pat) == 0: raise Exception(f"Prefix {prefix} is not defined!")
		r = re.compile(f"{prefix}|{pat[0]}")
		morphs = [m for m in morphs if r.match(m)] ## Only match at start
	## Reduce by infixes, if any
	if infix is not None:
		pat = [x[3] for x in infixes if x[0] == infix]
		if len(pat) == 0: raise Exception(f"Infix {infix} is not defined!")
		r = re.compile(re.escape(infix) + "|" + re.escape(pat[0]) + "(\.|$)")
		#print(f">>[Infix]: " + re.escape(infix) + "|" + re.escape(pat[0]))
		morphs = [m for m in morphs if r.search(m)]
	## Reduce by suffixes, if any
	if suffix is not None: ## Only match at end
		if type(suffix).__name__ == "str": suffix = [suffix, None]
		(_suffix, oc) = suffix
		pat = [x[3] for x in suffixes if x[0] == _suffix]
		if oc is not None: _suffix = oc if _suffix is None else _suffix+oc
		elif len(pat) == 0: raise Exception(f"_suffix {_suffix} is not defined!")
		if oc is None: _suffix += "(_op|_cl)"
		# The single length vocals cause problems, so combine with the infix
		if isVocal: _suffix = infix + _suffix
		r = re.compile(f"{_suffix}$")
		morphs = [m for m in morphs if r.search(m)]
	if verbose: print(f">> " + str(morphs))
	if len(morphs) == 0: return []
	if value is not None: return [(m, value) for m in morphs]
	return morphs

###########################
def emotionalize(pmx, input_file_name: str, write_model = True, moreinfo = False):
	"""
Utilizes the emotion morphs extracted from KK to construct TDA morphs.

[Output]: name + "_emote"
	"""
	state["moreinfo"] = moreinfo or DEBUG
	####
	CH__KK = 0; CH__TDA = 1;
	choices = [
		#("Generic            -- Combine all morphs based on their KK name", CH__KK),
		("TDA                -- Try to assemble morphs resembling TDA", CH__TDA),
		]
	choice = CH__TDA#util.ask_choices("Select the target collection", choices)
	####
	if choice == CH__KK: collect_KK(pmx)
	if choice == CH__TDA: add_TDA(pmx)
	return kklib.end(pmx if write_model else None, input_file_name, "_emote", ["Mode: " + str(choice)])

def collect_KK(pmx):
	### -- Just collect all matching and add them with e m b suffixes (or prefixes)
	##--- Group face, sirome, eye_line_l, eye_line_u into [eye]
	##--- Group lip, teeth, canine, tongue into [mouth]
	## -- Group mayuge into [eyebrow]
	pass

def add_TDA(pmx):
	addOrReplaceEye   = lambda jp,en,it: addOrReplace(pmx, jp, en, 2, it)
	addOrReplaceMouth = lambda jp,en,it: addOrReplace(pmx, jp, en, 3, it)
	addOrReplaceBrow  = lambda jp,en,it: addOrReplace(pmx, jp, en, 1, it)
	addOrReplaceOther = lambda jp,en,it: addOrReplace(pmx, jp, en, 4, it)
	## Avoid excessive collection of morphs again and again
	morphs = [m.name_jp for m in pmx.morphs]
	### Eyes ----------------------------
	def eyes():
		#????????????			mabataki			Blink			C	Close eyes (Up full = 100% 0%)
		#??????			warai				Laughter		C	Close eyes (Lids meet at center = 50 50)
		#????????????			winku				Wink			CO	Close left (5050)
		#???????????????			winku R				Wink R			OC	Close right (5050)
		#???????????????			Winku 2				Wink 2			CO	Close left (100 0)
		#??????????????????			Winku 2 R			Wink 2 R		OC	Close right (0 100)
		#?????????			nagomi				Softing			C	Close both (80 20) ??? Hor eyes
		#??????				ha					<emphasis>		C	">.<" ??? Upper brow from inside
		#????????????			bikkuri				Surprise		O	???0.0??? ??? Lids go outwards
		#?????????			jitome				Disgust			O	Upper goes 33% (is hor)
		#?????????			kiri				???click???			O	Inner Angle pulled down
		#????????????			hachiyume			Hachu eyes		*	???White with fuzzy black border???
		#?????????????????????		??? tatetsubure		Vert. Squint	*	: ^ Squint Vert
		#?????????????????????		??? yokotsubure		Hort Squint		*	: ^ Squint Hor
		pass
	# def: Search all morphs with "_winkl" in their name -- Could also search for the alternative name in case it was renamed
	addOrReplaceEye("????????????",   "Blink",  find_all_morphs(morphs, "eye", "_def", [None,"_cl"], 0.5) )
	addOrReplaceEye("??????",   "Smile",  find_all_morphs(morphs, "eye", "_egao", [None,"_cl"], 0.5) )
	addOrReplaceEye("????????????",   "Wink",  find_all_morphs(morphs, "eye", "_winkl", None, 0.5) )
	addOrReplaceEye("???????????????", "Wink R",  find_all_morphs(morphs, "eye", "_winkr", None, 0.5) )
	addOrReplaceEye("???????????????",  "Wink 2",  find_all_morphs(morphs, "eye", "_winkl", None, 0.75) )   # technically [def]
	addOrReplaceEye("??????????????????", "Wink 2 R",  find_all_morphs(morphs, "eye", "_winkr", None, 0.75) ) # technically [def]
	#addOrReplaceEye("?????????", "...",  find_all_morphs(morphs, "eye", "_winkr", None, 0.8) )
	#addOrReplaceEye("<ha>", "...",  find_all_morphs(morphs, "eye", "_winkr", None, 0.8) )
	addOrReplaceEye("?????????", "Disgust",  find_all_morphs(morphs, "eye", "_keno", None, 0.5) )
	# kiri
	#############
	def mouth():
		#	???				a					Say "A"			O	Open L+T for A
		#	???				I					Say "I"			*	Wide Op L for I
		#	???				u					Say "U"			O	Open L+T for U
		#	???				e					Say "E"			O	Open L+T for E
		#	???				o					Say "O"			O	Open L+T for O
		#	??????				a2					Say "A" (big)	O	Open WIDE for A
		#	???				n					Say ???N???			C	MC for N
		#	???				*					???????				O	L as-such, X infront of T+Z
		#	???				*					???????				C	L as-such ??? T open, Z pulls back
		#	???				*					???????				O	Same as ???
		#	???				*					Say ???Wa???		O	Looks like :D with barely T
		#	??				*					[Form]			C	L into shape
		#	?????				*									O	L into shape, T behind L
		#	?????????			niyari				Grin			C	M widens (flat smile)
		#	????????????			Niyari 2			Grin 2			C	Left MC high up
		#	????????????			nikkori				Smirk			C	????????? (almost creepy smile)
		#	?????????			pero				Lick			~~	T+L barely, Z out 50%
		#	????????????			tehepero			Happy ???bleh???	C	Venti ???Tehe??? (Like Grin2, but Z in it)
		#	???????????????			tehepero2			Happy ???bleh???	C	Same, but Z points down
		#	????????????			koukaku age			Raise MC		C	MC up
		#	????????????			koukaku sage		Lower MC		C	MC down
		#	????????????			kuchiyoko hiroge	Widen M			C	Very wide M
		#	????????????			hanashijou			No UpT			C	Up T is gone
		#	????????????			hanashimoto			No DwT			C	Dw T is gone
		#	????????????			hansamu				Handsome			Transform Chin
		pass
	defT_Op = find_one_morph(morphs, "kuti_ha.ha00_def_op")
	defZ_Op = find_one_morph(morphs, "kuti_sita.t00_def_op")
	addOrReplaceMouth("???", "A",  find_all_morphs(morphs, "kuti", "_a", "_s", 1.0, True) )
	addOrReplaceMouth("???", "I",  find_all_morphs(morphs, "kuti", "_i", "_s", 0.75, True) )
	addOrReplaceMouth("???", "U",  find_all_morphs(morphs, "kuti", "_u", "_s", 0.75, True) + [ (defT_Op, 0.75) ])
	addOrReplaceMouth("???", "E",  find_all_morphs(morphs, "kuti", "_e", "_s", 1.0, True) )
	addOrReplaceMouth("???", "O", find_all_morphs(morphs, "kuti", "_o", "_s", 0.75, True)	+ [ (defT_Op, 0.75) ])
	addOrReplaceMouth("??????", "A (Large)",  find_all_morphs(morphs, "kuti", "_a", "_l", 1.0, True) )
	addOrReplaceMouth("???", "N",  find_all_morphs(morphs, "kuti", "_n", "_s", 1.0, True) )
	addOrReplaceMouth("???", "???????", 
		find_all_morphs(morphs, "kuti", "_san", None, 0.5) + [(defT_Op, 1.0)])
#	addOrReplaceMouth("???", "???????",  find_all_morphs(morphs, "kuti", "_keno", None, 0.5) )
#	addOrReplaceMouth("???", "???????",  find_all_morphs(morphs, "kuti", "_keno", None, 0.5) )
#	addOrReplaceMouth("???", "Wa",  find_all_morphs(morphs, "kuti", "_keno", None, 0.5) )
	addOrReplaceMouth("??", "??????",  find_all_morphs(morphs, "kuti", "_neko", [None,"_cl"], 0.5) )
#	addOrReplaceMouth("?????", "?????? (Open)",  find_all_morphs(morphs, "kuti", "_keno", None, 0.5) )
#	addOrReplaceMouth("?????????", "Disgust",  find_all_morphs(morphs, "kuti", "", None, 0.5) )
#	addOrReplaceMouth("????????????", "Disgust",  find_all_morphs(morphs, "kuti", "_keno", None, 0.5) )
#	addOrReplaceMouth("????????????	", "Disgust",  find_all_morphs(morphs, "kuti", "_keno", None, 0.5) )
#	addOrReplaceMouth("?????????", "Licking",  find_all_morphs(morphs, "kuti", "_pero", None, 0.5) ) ##>> Fix or off
#	addOrReplaceMouth("????????????", "Disgust",  find_all_morphs(morphs, "kuti", "_keno", None, 0.5) )
#	addOrReplaceMouth("???????????????", "Disgust",  find_all_morphs(morphs, "kuti", "_keno", None, 0.5) )
	addOrReplaceMouth("????????????", "Be Happy", [find_one_morph(morphs, "kuti_face.f00_uresi_cl", 0.5)])
	addOrReplaceMouth("????????????", "Be Sad", [find_one_morph(morphs, "kuti_face.f00_ikari_cl", 1.0)])
#	addOrReplaceMouth("????????????", "Disgust",  find_all_morphs(morphs, "kuti", "_keno", None, 0.5) )
#	addOrReplaceMouth("????????????", "Disgust",  find_all_morphs(morphs, "kuti", "_keno", None, 0.5) )
#	addOrReplaceMouth("????????????", "Disgust",  find_all_morphs(morphs, "kuti", "_keno", None, 0.5) )
	#############
	addOrReplaceBrow("?????????", "Serious",  find_all_morphs(morphs, "mayuge", "_sinken", [None,"_cl"], 1) )
	addOrReplaceBrow("??????", "Worried",  find_all_morphs(morphs, "mayuge", "_koma", [None, "_cl"], 1) )
#	addOrReplaceBrow("???", "Eyebrow up",  find_all_morphs(morphs, "mayuge", "_komaru", None, 1) )
	addOrReplaceBrow("???", "Eyebrow down",  [find_one_morph(morphs, "mayuge.mayu00_def_cl", 1.0)])
	#############
	addOrReplaceOther("??????", "Angry", [
		find_one_morph(morphs, "eye_face.f00_ikari_op", 0.5),
		find_one_morph(morphs, "eye_nose.nl00_ikari_op", 0.5),
		find_one_morph(morphs, "eye_siroL.sL00_ikari_op", 0.5),
		find_one_morph(morphs, "eye_siroR.sR00_ikari_op", 0.5),
		find_one_morph(morphs, "eye_line_u.elu00_ikari_op", 0.5),
		find_one_morph(morphs, "eye_line_l.ell00_ikari_op", 0.5),
		find_one_morph(morphs, "kuti_face.f00_ikari_cl", 1.0),
		find_one_morph(morphs, "mayuge.mayu00_oko_cl", 1.0),
		])
	
	names = [
		"???","???","???","???","???","??????","???",# Talking
		"????????????","??????","????????????","???????????????","???????????????","??????????????????","?????????", # Eyes
		"???","??","????????????","????????????","??????", # Mouth
		"?????????","??????","???", # Mayuge
		]
	print("\n-- Add Vocals to combined group 'TrackVoice'...")
	frames = [find_morph(pmx, name, True) for name in names]
	frames = [[1,idx] for idx in frames if idx != -1]
	name = "TrackVoice"
	idx = find_disp(pmx, name, False)
	if idx != -1: pmx.frames[idx].items = frames
	else: pmx.frames.append(pmxstruct.PmxFrame(name, name, False, frames))
	
	#############
	pass
########
