# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

bl_info = {
    "name": "Sync Material to Strips",
    "author": "Nick Alberelli",
    "description": "Creates Sequencer Strips that are linked to Image Texture nodes. Syncronize node in material with start frame from a Sequencer Strip.",
    "blender": (3, 3, 0),
    "version": (1, 0, 0),
    "category": "Video Tools",
}


import bpy


def get_free_channels(sequence_editor: bpy.types.SequenceEditor) -> int:
    """Find the highest used channel in the sequence editor"""
    channels = set([seq.channel for seq in sequence_editor.sequences_all])
    if channels:
        return max(channels)
    else:
        return 0


def material_node_get(mat: bpy.types.Material, node_name: str) -> bpy.types.Node:
    """Returns node of a given name"""
    return mat.node_tree.nodes[node_name]


def get_image_nodes(mat: bpy.types.Material) -> list[bpy.types.Node]:
    """Return list of image texture nodes"""
    if mat and mat.node_tree:
        return [node for node in mat.node_tree.nodes if node.type == "TEX_IMAGE"]
    return


def get_sequence_editor(scene: bpy.types.Scene) -> bpy.types.SequenceEditor:
    """Find suitable sequence editor in current scene"""
    if not scene.sequence_editor:
        scene.sequence_editor.create()
    return scene.sequence_editor


def create_sequence_from_image_node(
    seq_editor: bpy.types.SequenceEditor, node: bpy.types.Node, mat: bpy.types.Material
) -> bpy.types.MovieSequence:
    """Create strip to linked image textures start frame/duration"""
    channel = get_free_channels(seq_editor) + 1
    strip = seq_editor.sequences.new_movie(
        node.image.name,
        node.image.filepath,
        channel,
        node.image_user.frame_start,
        fit_method="FILL",
    )
    strip.mat_sync.material = mat
    strip.mat_sync.node_name = node.name
    strip.mat_sync.strip_name = strip.name
    return strip


def syncronize_strip_to_image_node(strip: bpy.types.MovieSequence):
    """Syncronize Material's Image Texture Start frame with Strip"""
    image_node = strip.mat_sync.material.node_tree.nodes[strip.mat_sync.node_name]
    image_node.image_user.frame_duration = int(strip.frame_duration)
    image_node.image_user.frame_start = int(strip.frame_start)


def syncronize_all_strips_to_image_nodes(sequence_editor: bpy.types.SequenceEditor):
    """Syncronize all Strips to their Materials"""
    for strip in sequence_editor.sequences_all:
        if (
            strip.type == "MOVIE"
            and strip.mat_sync.material
            and strip.mat_sync.node_name
        ):
            syncronize_strip_to_image_node(strip)


class SEQ_AS_PLANE_OT_link(bpy.types.Operator):
    bl_idname = "seq_as_plane.link"
    bl_label = "Sync Material to New Strip"
    bl_description = "Create strip to syncroniz to this material's image texture node"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context):
        col = self.layout.column(align=False)
        col.prop(context.window_manager, "output_scene")

    def execute(self, context):
        scene = context.window_manager.output_scene
        seq_editor = get_sequence_editor(scene)
        obj = context.active_object
        mat = obj.active_material
        nodes = get_image_nodes(mat)

        # Check list is one node long
        if len(nodes) != 1:
            self.report(
                {"ERROR"},
                f"There are {len(nodes)} Image Texture nodes. There must be exactly 1 node to syncronize.",
            )
            return {"CANCELLED"}
        node = nodes[0]
        image = node.image
        # Ensure image node is using a movie file
        if image.source != "MOVIE":
            self.report(
                {"ERROR"},
                f"Node {node.name} is not using movie.",
            )
            return {"CANCELLED"}

        for strip in seq_editor.sequences_all:
            if strip.mat_sync.material == mat:
                self.report(
                    {"ERROR"},
                    f"Material already linked to Strip '{strip.name}'.",
                )
                return {"CANCELLED"}

        new_strip = create_sequence_from_image_node(seq_editor, node, mat)
        self.report(
            {"INFO"},
            f"Material '{new_strip.mat_sync.material.name}' is now linked to Sequence Strip '{new_strip.name}'",
        )
        return {"FINISHED"}


class SEQ_AS_PLANE_PT_link(bpy.types.Panel):
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_idname = "SEQ_AS_PLANE_PT_link"
    bl_label = "Sync Material"

    def draw(self, context):
        row = self.layout.row(align=True)
        row.operator("seq_as_plane.link", icon="PLUS")
        row.prop(
            context.window_manager,
            "auto_sync_materials_to_strips",
            icon="UV_SYNC_SELECT",
            text="",
        )


def header_mat_add_to_seq(self, context):
    self.layout.operator("seq_as_plane.link", icon="PLUS")


def header_mat_to_seq(self, context):
    layout = self.layout
    col = layout.column(align=(False))
    col.prop(
        context.window_manager,
        "auto_sync_materials_to_strips",
        icon="UV_SYNC_SELECT",
    )


class SEQ_AS_PLANE_PT_panel(bpy.types.Panel):
    bl_space_type = "SEQUENCE_EDITOR"
    bl_region_type = "UI"
    bl_idname = "SEQ_AS_PLANE_PT_panel"
    bl_label = "Sync Material"
    bl_category = "Strip"

    @classmethod
    def poll(cls, context):
        strip = context.active_sequence_strip
        if not strip:
            return False
        return strip.type == "MOVIE"

    def draw(self, context):
        self.layout.prop(context.window_manager, "auto_sync_materials_to_strips")
        strip = context.active_sequence_strip
        if not strip:
            return
        box = self.layout.box()
        box.label(text=strip.name, icon="FILE_MOVIE")
        row = box.row()
        row.prop(strip.mat_sync, "is_synced", text="", icon="UV_SYNC_SELECT")
        row.prop(strip.mat_sync, "material", text="")


class SEQ_AS_PLANE_settings(bpy.types.PropertyGroup):
    material: bpy.props.PointerProperty(type=bpy.types.Material)
    node_name: bpy.props.StringProperty()
    strip_name: bpy.props.StringProperty()

    def check_sync_status(self):
        if self.material and self.strip_name and self.node_name:
            image_node = self.material.node_tree.nodes[self.node_name]
            source_strip = self.id_data.sequence_editor.sequences.get(self.strip_name)
            if source_strip and image_node.image_user.frame_start == int(
                source_strip.frame_start
            ):
                return True
        return False

    def set_sync_status(self, context):
        if self.material and self.strip_name:
            strip = self.id_data.sequence_editor.sequences[self.strip_name]
            syncronize_strip_to_image_node(strip)
        return None

    is_synced: bpy.props.BoolProperty(
        name="is_synced",
        get=check_sync_status,
        set=set_sync_status,
        options=set(),
        description="",
    )


classes = (
    SEQ_AS_PLANE_OT_link,
    SEQ_AS_PLANE_settings,
    SEQ_AS_PLANE_PT_panel,
    SEQ_AS_PLANE_PT_link,
)


@bpy.app.handlers.persistent
def update_materials_via_sequence(self, context):
    if bpy.data.window_managers[0].auto_sync_materials_to_strips:
        for scene in bpy.data.scenes:
            if scene.sequence_editor:
                syncronize_all_strips_to_image_nodes(scene.sequence_editor)


def register():
    for i in classes:
        bpy.utils.register_class(i)
    bpy.types.MovieSequence.mat_sync = bpy.props.PointerProperty(
        type=SEQ_AS_PLANE_settings
    )
    bpy.app.handlers.depsgraph_update_post.append(update_materials_via_sequence)
    bpy.types.WindowManager.auto_sync_materials_to_strips = bpy.props.BoolProperty(
        name="Auto Sync Material Strips",
        default=False,
        description="Sync all Material Strips to their given Materials",
    )
    bpy.types.WindowManager.output_scene = bpy.props.PointerProperty(
        name="Scene",
        description="Create Strip within selected Scene",
        type=bpy.types.Scene,
    )
    bpy.types.SEQUENCER_HT_header.append(header_mat_to_seq)
    # bpy.types.EEVEE_MATERIAL_PT_context_material.append(header_mat_add_to_seq)


def unregister():
    for i in classes:
        bpy.utils.unregister_class(i)
    bpy.app.handlers.depsgraph_update_post.remove(update_materials_via_sequence)
    del bpy.types.WindowManager.auto_sync_materials_to_strips
    del bpy.types.WindowManager.output_scene
    bpy.types.SEQUENCER_HT_header.remove(header_mat_to_seq)
    # bpy.types.EEVEE_MATERIAL_PT_context_material.remove(header_mat_add_to_seq)
