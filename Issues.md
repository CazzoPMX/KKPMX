
# Known Issues





## Troubleshooting


This section contains a list of known issues, and how to solve them.


### MMD issues


| MMD crashes when loading | |
| --- | --- |
| [Display-Frames] contain '-1' entries | Export-Issue fixed by (1-Cleanup) |
| VertexMorphs link to non-existing indices | Export-Issue fixed by (1-Cleanup) |
| Joints missing one or both Rigids |     |

| MMD crashes randomly | |
| --- | --- |
| Sometimes caused by Physics caclulation. |     |

| Other | |
| --- | --- |
| Non-see-through layers while fading out | Put Materials in correct order (inside index < outside index |
| Unable to see facial frames | Add missing Material-Morphs to [Facials] Frame |
| [Facials] tab takes long to load | Remove the [Expression] morphs from [Facials].<br/>Done by (3:Material-Morphs) |
| Vibrating chest physics | Locate the 'stick' Rigids and set ROT.Z = max:1 min:0 |
| Bones and Physics are connected all over the place | Caused by auto-rigging accessories. You need to clean up the weird stuff manually. |
| Hair flies away like paper lanterns | Physics chains need two solid segments to stay where they are. (At least they didn't stay unless I did that) |

## Open Issues


Things that are worked on or haven't been fixed yet.

 - Extra textures for face are ignored. -- overtex2 stays optional
 - White-ish overtex1 is barely visible. -- Fixed partially
 - Knee looks broken when kneeling too much.