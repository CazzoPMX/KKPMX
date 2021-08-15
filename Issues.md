
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
| Non-see-through layers while fading out | Put Materials in correct order |
| Unable to remove facial frames | Add missing Material-Morphs to [Facials] Frame |
| [Facials] tab takes long to load | Remove the [Expression] morphs from [Facials].<br/>Done by (3:Material-Morphs) |
| Vibrating chest physics | Locate the 'stick' Rigids and set ROT.Z = max:1 min:0 |

## Open Issues


Things that are worked on or haven't been fixed yet.

 - LineMask is ignored.
 - Extra textures for face are ignored.
 - Iris can look weird (because incorrect or ignoring offset / scale).
 - White-ish overtex1 is barely visible.
 - Knee looks broken when kneeling too much.