
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
| Bones and Physics are connected all over the place | Because there is no enforced naming convention for custom accessories except for the start,<br/>most accessories (except a certain few groups) are rigged as "all in a line".<br/>Besides a certain few exceptions that added a big enough number of assets (like hair mods),<br/>most will therefore be all over the place, especially if they are imported from another game.<br/>Manual clean up and properly cutting into segments is required for proper use of most other cases. |
| Hair flies away like paper lanterns | Physics chains need two solid segments to stay where they are. (At least they didn't stay unless I did that) |
| Some Textures have wrong colors | If texture color is supplied through the texture itself, the default color usually stays, which is then applied as 'expected' through Color & DetailMask. Delete the masks which cause the problems and run Mode:3 (Property Parser) again (or repair the filepaths manually yourself. |
| Eyes have wrong offset | Depending on weird internals, the 'idle' position of the eyes without blinking or following can be such that the Render-State exports that with -0.1 resp. 0.1. Just replace them in 'cf_m_hitomi_00#-<<number>>'.Offset with 0.0 (or at least equal on both 'hitomi' entries, if they are bigger.). Same for scale |

## Open Issues


Things that are worked on or haven't been fixed yet.

 - Extra textures for face are ignored. -- overtex2 stays optional
 - White-ish overtex1 is barely visible. -- Fixed partially
 - Knee looks broken when kneeling too much.