# Nuthouse01 - 10/10/2020 - v5.03
# This code is free to use and re-distribute, but I cannot be held responsible for damages that it may or may not cause.
#####################

# first, import system stuff
import copy

# second, wrap custom imports with a try-except to catch it if files are missing
try:
	# these imports work if running from GUI
	from . import nuthouse01_core as core
	from . import nuthouse01_pmx_parser as pmxlib
	from . import nuthouse01_pmx_struct as pmxstruct
except ImportError as eee:
	try:
		# these imports work if running from double-click on THIS script
		import nuthouse01_core as core
		import nuthouse01_pmx_parser as pmxlib
		import nuthouse01_pmx_struct as pmxstruct
	except ImportError as eee:
		print(eee.__class__.__name__, eee)
		print("ERROR: failed to import some of the necessary files, all my scripts must be together in the same folder!")
		print("...press ENTER to exit...")
		input()
		exit()
		core = pmxlib = pmxstruct = None


# when debug=True, disable the catchall try-except block. this means the full stack trace gets printed when it crashes,
# but if launched in a new window it exits immediately so you can't read it.
DEBUG = False


# just take a wild guess what this field controls
PRINT_AFFECTED_MORPHS = False

# TODO: reconsider whether zeroing out tex/toon/alpha is really necessary/helpful/correct... YYB doesn't do it
# opacity, edge size, edge alpha, tex, toon, sph
# template =          [0, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0]
template = pmxstruct.PmxMorphItemMaterial(
	mat_idx=999, is_add=0, diffRGB=[1,1,1], specRGB=[1,1,1],ambRGB=[1,1,1], specpower=1, edgeRGB=[1,1,1], 
	alpha=0, edgealpha=0, edgesize=0, texRGBA=[1,1,1,1], sphRGBA=[1,1,1,1], toonRGBA=[1,1,1,1]
)
# the above template multiplies everything by 0, 
# this gets the same result by subtracting 1 from everthing
# template_minusone = [1, 0, 0, 0, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -1, -1, 0, 0, 0, -1, 0, 0, 0, -1, 0, 0, 0, -1]
template_minusone = pmxstruct.PmxMorphItemMaterial(
	mat_idx=999, is_add=1, diffRGB=[0,0,0], specRGB=[0,0,0],ambRGB=[0,0,0], specpower=0, edgeRGB=[0,0,0],
	alpha=-1, edgealpha=-1, edgesize=-1, texRGBA=[0,0,0,0], sphRGBA=[0,0,0,0], toonRGBA=[0,0,0,0]
)


helptext = '''====================
alphamorph_correct:
This function fixes improper "material hide" morphs in a model.
Many models simply set the opacity to 0, but forget to zero out the edging effects or other needed fields.
This also changes all alphamorphs to use the "multiply by 0" approach when the target material is opaque(visible) by default, and use the "add -1" approach when the target is transparent(hidden) by default.
'''

iotext = '''Inputs:  PMX file "[model].pmx"\nOutputs: PMX file "[model]_alphamorph.pmx"
'''

def showhelp():
	# print info to explain the purpose of this file
	core.MY_PRINT_FUNC(helptext)
def showprompt():
	# print info to explain what inputs/outputs it needs/creates
	core.MY_PRINT_FUNC(iotext)
	
	# prompt PMX name
	core.MY_PRINT_FUNC("Please enter name of PMX model file:")
	input_filename_pmx = core.prompt_user_filename(".pmx")
	pmx = pmxlib.read_pmx(input_filename_pmx, moreinfo=True)
	return pmx, input_filename_pmx

def alphamorph_correct(pmx: pmxstruct.Pmx, moreinfo=False):
	num_fixed = 0
	total_morphs_affected = 0
	
	# for each morph:
	for d,morph in enumerate(pmx.morphs):
		# if not a material morph, skip it
		if morph.morphtype != 8: continue
		this_num_fixed = 0
		# for each material in this material morph:
		for dd,matitem in enumerate(morph.items):
			matitem:pmxstruct.PmxMorphItemMaterial  # type annotation for pycharm
			# if (mult opacity by 0) OR (add -1 to opacity), then this item is (trying to) hide the target material
			if (not matitem.is_add and matitem.alpha == 0) or (matitem.is_add and matitem.alpha == -1):
				# then replace the entire set of material-morph parameters
				# opacity, edge size, edge alpha, tex, toon, sph
				if matitem.mat_idx != -1 and pmx.materials[matitem.mat_idx].alpha == 0:
					# if the target material is initially transparent, replace with add-negative-1
					t = template_minusone
				else:
					# if the target material is initally opaque, or targeting the whole model, replace with mult-by-0
					t = template
				if matitem.list()[1:] != t.list()[1:]:  # if it is not already good,
					newitem = copy.deepcopy(t)
					newitem.mat_idx = matitem.mat_idx
					morph.items[dd] = newitem  # replace the morph with the template
					this_num_fixed += 1
					
		if this_num_fixed != 0:
			total_morphs_affected += 1
			num_fixed += this_num_fixed
			if moreinfo:
				core.MY_PRINT_FUNC("morph #{:<3} JP='{}' / EN='{}', fixed {} items".format(
					d, morph.name_jp, morph.name_en, this_num_fixed))
	
	if num_fixed:
		core.MY_PRINT_FUNC("Fixed %d 'hide' morphs" % total_morphs_affected)


	# identify materials that start transparent but still have edging
	mats_fixed = 0
	for d,mat in enumerate(pmx.materials):
		# if opacity is zero AND edge is enabled AND edge has nonzero opacity AND edge has nonzero size
		if mat.alpha == 0 and mat.flaglist[4] and mat.edgealpha != 0 and mat.edgesize != 0:
			this_num_edgefixed = 0
			# THEN check for any material morphs that add opacity to this material
			for d2,morph in enumerate(pmx.morphs):
				# if not a material morph, skip it
				if morph.morphtype != 8: continue
				# for each material in this material morph:
				for matitem in morph.items:
					# if not operating on the right material, skip it
					if matitem.mat_idx != d: continue
					# if adding and opacity > 0:
					if matitem.is_add == 1 and matitem.alpha > 0:
						# set it to add the edge amounts from the material
						matitem.edgealpha = mat.edgealpha
						matitem.edgesize =  mat.edgesize
						this_num_edgefixed += 1
			# done looping over morphs
			# if it modified any locations, zero out the edge params in the material
			if this_num_edgefixed != 0:
				mat.edgealpha = 0
				mat.edgesize = 0
				num_fixed += this_num_edgefixed
				mats_fixed += 1
				if moreinfo:
					core.MY_PRINT_FUNC("mat #{:<3} JP='{}' / EN='{}', fixed {} appear morphs".format(
						d, mat.name_jp, mat.name_en, this_num_edgefixed))
	
	if mats_fixed:
		core.MY_PRINT_FUNC("Removed edging from %d initially hidden materials" % mats_fixed)
	
	if num_fixed == 0 and mats_fixed == 0:
		core.MY_PRINT_FUNC("No changes are required")
		return pmx, False
	
	return pmx, True

def end(pmx, input_filename_pmx):
	# write out
	# output_filename_pmx = "%s_alphamorph.pmx" % core.get_clean_basename(input_filename_pmx)
	output_filename_pmx = input_filename_pmx[0:-4] + "_alphamorph.pmx"
	output_filename_pmx = core.get_unused_file_name(output_filename_pmx)
	pmxlib.write_pmx(output_filename_pmx, pmx, moreinfo=True)
	return None

def main():
	showhelp()
	pmx, name = showprompt()
	pmx, is_changed = alphamorph_correct(pmx, PRINT_AFFECTED_MORPHS)
	if is_changed:
		end(pmx, name)
	core.pause_and_quit("Done with everything! Goodbye!")

if __name__ == '__main__':
	core.MY_PRINT_FUNC("Nuthouse01 - 10/10/2020 - v5.03")
	if DEBUG:
		main()
	else:
		try:
			main()
		except (KeyboardInterrupt, SystemExit):
			# this is normal and expected, do nothing and die normally
			pass
		except Exception as ee:
			# if an unexpected error occurs, catch it and print it and call pause_and_quit so the window stays open for a bit
			core.MY_PRINT_FUNC(ee)
			core.pause_and_quit("ERROR: something truly strange and unexpected has occurred, sorry, good luck figuring out what tho")
