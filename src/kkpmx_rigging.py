# Cazoo - 2021-06-27
# This code is free to use and re-distribute, but I cannot be held responsible for damages that it may or may not cause.
#####################
import json
import re
import os
from typing import List, Union

import nuthouse01_core as core
import nuthouse01_pmx_struct as struct
import morph_scale
import kkpmx_utils as util
from kkpmx_utils import find_bone, find_mat, find_disp, find_morph, find_rigid

###############
### Riggers ###
###############

def transform_skirt(pmx):
	sizer = [0,0,0]
	for rigid in pmx.rigidbodies:
		## Change width of all but [05] to XX (start at 0.6)
		if not re.match(r"cf_j_sk", rigid.name_jp): continue
		if re.match(r"cf_j_sk_\d\d_05", rigid.name_jp): continue
		## Change mode to 1 & set depth to 0.02
		rigid.shape = 1
		rigid.size[0] = 0.6
		rigid.size[2] = 0.02
	for joint in pmx.joints:
		if not re.match(r"cf_j_sk", joint.name_jp): continue
		if re.match(r"cf_j_sk_\d\d_05", joint.name_jp): continue
		if re.match(r"cf_j_sk_\d\d_\d\d\[side\]", joint.name_jp):
			rigid = pmx.rigidbodies[joint.rb1_idx]
			## X pos requires using triangulation, maybe later
			joint.pos[1] = rigid.pos[1] + rigid.size[1] / 2
			joint.pos[2] = rigid.pos[2] + rigid.size[2] / 2
	
		## Delete Side Joints of [05]
		## Move Side Joints to sides (X + width / 2, Y + height / 2)
########
	pass
