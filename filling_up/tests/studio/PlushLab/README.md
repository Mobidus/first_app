# PlushLab (T08) — NOT_RUN in this environment

Requires the Mallow mesh to be imported first (assets/import/models/toy_plush_mallow.fbx or .glb,
3D Importer, keep rig + skinning; measure the imported bounding box: 12 x 5 x 10 studs W x H x D).
Put the imported MeshPart (with its Bones) inside the `PlushVisual` model produced by
PropFactory (replace the proxy part) and set its `LocalOffset` attribute.

Play with `FU_TEST_SUITE = "plush"`. Then, on the client (F9 console), verify:
* during impact: belly bones translate, Head/Arm/Leg rotate, no bone scale, top >= 0.72 height;
* after 0.9 s: every `Bone.Transform` equals the identity (no drift) — repeat after 100 cycles;
* stand on Mallow: feet vs visible top <= 0.25 stud (measure with a raycast to the mesh);
* toggle reduced effects: KO and rewards identical (they never read PlushPose).
Record numbers in reports/plush_stress.json (`studio` section) with device names.
