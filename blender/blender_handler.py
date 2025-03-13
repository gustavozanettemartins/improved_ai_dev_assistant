#!/usr/bin/env python3

import os
import sys
import json
import tempfile
import subprocess
import asyncio
import aiofiles
from typing import Dict, List, Any, Optional, Tuple

from config.config_manager import config_manager, logger
from core.performance import perf_tracker


class BlenderHandler:
    """Handles interactions with Blender's Python API."""

    def __init__(self, blender_path: str = None):
        """
        Initialize the BlenderHandler.

        Args:
            blender_path: Path to the Blender executable. If None, will try to get from config or find automatically.
        """
        # First check if there's a path in the config
        config_blender_path = config_manager.get("blender_path")

        self.blender_path = blender_path or config_blender_path or self._find_blender_path()
        self.has_blender = self.blender_path is not None and os.path.exists(self.blender_path)

        if self.has_blender:
            logger.info(f"BlenderHandler initialized with Blender at: {self.blender_path}")
        else:
            logger.warning("Blender not found, functionality will be limited")

    def _find_blender_path(self) -> Optional[str]:
        """
        Attempt to find the Blender executable path automatically.

        Returns:
            Path to Blender executable or None if not found
        """
        # Common Blender paths by platform
        possible_paths = []

        if sys.platform == "win32":
            # Windows
            program_files = [os.environ.get("ProgramFiles", "C:\\Program Files"),
                             os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")]

            for pf in program_files:
                for version in ["3.6", "3.5", "3.4", "3.3", "3.2", "3.1", "3.0", "2.93"]:
                    possible_paths.append(os.path.join(pf, "Blender Foundation", f"Blender {version}", "blender.exe"))

        elif sys.platform == "darwin":
            # macOS
            possible_paths = [
                "/Applications/Blender.app/Contents/MacOS/Blender",
                os.path.expanduser("~/Applications/Blender.app/Contents/MacOS/Blender")
            ]

            # Also check versions
            for version in ["3.6", "3.5", "3.4", "3.3", "3.2", "3.1", "3.0", "2.93"]:
                possible_paths.append(f"/Applications/Blender {version}.app/Contents/MacOS/Blender")
                possible_paths.append(
                    os.path.expanduser(f"~/Applications/Blender {version}.app/Contents/MacOS/Blender"))

        else:
            # Linux and others
            possible_paths = [
                "/usr/bin/blender",
                "/usr/local/bin/blender",
                os.path.expanduser("~/blender-extracted/blender")
            ]

        # Try to find Blender in PATH
        try:
            result = subprocess.run(["which", "blender"] if sys.platform != "win32" else ["where", "blender"],
                                    capture_output=True, text=True, check=False)
            if result.returncode == 0:
                possible_paths.insert(0, result.stdout.strip())
        except:
            pass

        # Check each path
        for path in possible_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                logger.info(f"Found Blender at: {path}")
                return path

        return None

    async def check_blender_connection(self) -> Tuple[bool, str]:
        """
        Check if Blender is available and can be executed.

        Returns:
            Tuple of (success: bool, message: str)
        """
        if not self.has_blender:
            return False, "Blender not found. Please set the blender_path in config or install Blender."

        try:
            # Run a simple Blender Python command to check if it works
            result = await asyncio.create_subprocess_exec(
                self.blender_path, "--background", "--python-expr", "import bpy; print('BLENDER_CONNECTION_OK')",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await result.communicate()
            stdout_str = stdout.decode(errors='replace')

            if "BLENDER_CONNECTION_OK" in stdout_str:
                return True, "Blender connection successful"
            else:
                return False, f"Blender test failed: {stdout_str}\n{stderr.decode(errors='replace')}"

        except Exception as e:
            logger.error(f"Error testing Blender connection: {e}")
            return False, f"Error testing Blender connection: {e}"

    async def create_object(self, obj_type: str, name: str = None, location: List[float] = None,
                            size: List[float] = None, rotation: List[float] = None,
                            material: Dict[str, Any] = None) -> Tuple[bool, str]:
        """
        Create a 3D object in Blender.

        Args:
            obj_type: Type of object to create (cube, sphere, plane, cylinder, cone, torus)
            name: Name for the new object
            location: [x, y, z] coordinates
            size: [x, y, z] dimensions
            rotation: [x, y, z] rotation in radians
            material: Material properties dictionary

        Returns:
            Tuple of (success: bool, message: str)
        """
        if not self.has_blender:
            return False, "Blender not found. Please set the blender_path in config or install Blender."

        perf_tracker.increment_counter("blender_operations")
        start_time = perf_tracker.start_timer("blender_create_object")

        # Default values
        name = name or f"{obj_type.capitalize()}"
        location = location or [0, 0, 0]
        rotation = rotation or [0, 0, 0]

        # Create temporary Python script
        script_fd, script_path = tempfile.mkstemp(suffix=".py", prefix="blender_create_")
        try:
            script_content = f"""
import bpy
import os
import json

# Clear default objects (optional)
#bpy.ops.object.select_all(action='SELECT')
#bpy.ops.object.delete()

# Create the object
if '{obj_type}' == 'cube':
    bpy.ops.mesh.primitive_cube_add(location=({location[0]}, {location[1]}, {location[2]}))
elif '{obj_type}' == 'sphere':
    bpy.ops.mesh.primitive_uv_sphere_add(location=({location[0]}, {location[1]}, {location[2]}))
elif '{obj_type}' == 'plane':
    bpy.ops.mesh.primitive_plane_add(location=({location[0]}, {location[1]}, {location[2]}))
elif '{obj_type}' == 'cylinder':
    bpy.ops.mesh.primitive_cylinder_add(location=({location[0]}, {location[1]}, {location[2]}))
elif '{obj_type}' == 'cone':
    bpy.ops.mesh.primitive_cone_add(location=({location[0]}, {location[1]}, {location[2]}))
elif '{obj_type}' == 'torus':
    bpy.ops.mesh.primitive_torus_add(location=({location[0]}, {location[1]}, {location[2]}))
else:
    raise ValueError(f"Unknown object type: {obj_type}")

# Get the object and rename it
obj = bpy.context.active_object
obj.name = '{name}'

# Set rotation (in radians)
obj.rotation_euler = ({rotation[0]}, {rotation[1]}, {rotation[2]})

"""

            # Add size if specified
            if size:
                script_content += f"""
# Set size
obj.scale = ({size[0]}, {size[1]}, {size[2]})
"""

            # Add material if specified
            if material:
                mat_color = material.get("color", [0.8, 0.8, 0.8, 1.0])
                mat_metallic = material.get("metallic", 0.0)
                mat_roughness = material.get("roughness", 0.5)

                script_content += f"""
# Create material
mat_name = '{name}_material'
mat = bpy.data.materials.new(mat_name)
mat.use_nodes = True
nodes = mat.node_tree.nodes

# Get the principled BSDF shader
principled = nodes.get('Principled BSDF')
if principled:
    principled.inputs['Base Color'].default_value = ({mat_color[0]}, {mat_color[1]}, {mat_color[2]}, {mat_color[3]})
    principled.inputs['Metallic'].default_value = {mat_metallic}
    principled.inputs['Roughness'].default_value = {mat_roughness}

# Assign material to object
if obj.data.materials:
    obj.data.materials[0] = mat
else:
    obj.data.materials.append(mat)
"""

            # Save the scene
            script_content += """
# Print success message with object details
print(f"BLENDER_SUCCESS: Created {obj.name} at location {obj.location}")

# Save current blend file if BLEND_FILE is specified
blend_file = os.environ.get('BLEND_FILE')
if blend_file:
    bpy.ops.wm.save_as_mainfile(filepath=blend_file)
    print(f"Saved file to {blend_file}")
"""

            # Write the script to the temporary file
            async with aiofiles.open(script_path, 'w') as f:
                await f.write(script_content)

            # Set environment variables
            env = os.environ.copy()

            # Determine if we need to save to a blend file
            blend_file = config_manager.get("blender_output_file", "")
            if blend_file:
                env["BLEND_FILE"] = blend_file

            # Execute Blender with the script
            process = await asyncio.create_subprocess_exec(
                self.blender_path, "--background", "--python", script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )

            stdout, stderr = await process.communicate()
            stdout_str = stdout.decode(errors='replace')
            stderr_str = stderr.decode(errors='replace')

            # Clean up the temporary script
            os.remove(script_path)

            # Check for success
            if "BLENDER_SUCCESS" in stdout_str:
                success_msg = [line for line in stdout_str.split('\n') if "BLENDER_SUCCESS" in line][0]
                perf_tracker.end_timer("blender_create_object", start_time)
                return True, success_msg.replace("BLENDER_SUCCESS: ", "")
            else:
                logger.error(f"Blender error: {stderr_str}")
                perf_tracker.end_timer("blender_create_object", start_time)
                return False, f"Error creating object in Blender: {stderr_str}"

        except Exception as e:
            try:
                os.remove(script_path)
            except:
                pass

            logger.error(f"Error in create_object: {e}")
            perf_tracker.end_timer("blender_create_object", start_time)
            return False, f"Error creating object: {e}"

    async def render_scene(self, output_path: str, width: int = 1920, height: int = 1080,
                           samples: int = 128, engine: str = 'CYCLES') -> Tuple[bool, str]:
        """
        Render the current Blender scene to an image file.

        Args:
            output_path: Path to save the rendered image
            width: Image width in pixels
            height: Image height in pixels
            samples: Render samples (higher = better quality but slower)
            engine: 'CYCLES' or 'EEVEE'

        Returns:
            Tuple of (success: bool, message: str)
        """
        if not self.has_blender:
            return False, "Blender not found. Please set the blender_path in config or install Blender."

        # Check if blend file exists
        blend_file = config_manager.get("blender_output_file", "")
        if not blend_file or not os.path.exists(blend_file):
            return False, "No Blender file to render. Create objects first."

        perf_tracker.increment_counter("blender_operations")
        start_time = perf_tracker.start_timer("blender_render")

        # Create temporary Python script
        script_fd, script_path = tempfile.mkstemp(suffix=".py", prefix="blender_render_")
        try:
            script_content = f"""
import bpy

# Set render settings
scene = bpy.context.scene
scene.render.resolution_x = {width}
scene.render.resolution_y = {height}

# Set render engine
scene.render.engine = '{engine}'
if '{engine}' == 'CYCLES':
    scene.cycles.samples = {samples}
    scene.cycles.device = 'GPU'

    # Try to enable GPU rendering if available
    preferences = bpy.context.preferences
    cycles_preferences = preferences.addons["cycles"].preferences

    try:
        # Enable CUDA or OptiX or Metal based on availability
        cycles_preferences.compute_device_type = 'CUDA'
        bpy.context.preferences.addons["cycles"].preferences.get_devices()
    except:
        try:
            cycles_preferences.compute_device_type = 'OPTIX'
            bpy.context.preferences.addons["cycles"].preferences.get_devices()
        except:
            try:
                cycles_preferences.compute_device_type = 'METAL'
                bpy.context.preferences.addons["cycles"].preferences.get_devices()
            except:
                # Fallback to CPU
                scene.cycles.device = 'CPU'

# Set the output path
scene.render.filepath = '{output_path}'
scene.render.image_settings.file_format = 'PNG'

# Render
bpy.ops.render.render(write_still=True)

print(f"BLENDER_RENDER_SUCCESS: Rendered image saved to {output_path}")
"""

            # Write the script to the temporary file
            async with aiofiles.open(script_path, 'w') as f:
                await f.write(script_content)

            # Execute Blender with the script
            process = await asyncio.create_subprocess_exec(
                self.blender_path, "--background", blend_file, "--python", script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()
            stdout_str = stdout.decode(errors='replace')
            stderr_str = stderr.decode(errors='replace')

            # Clean up the temporary script
            os.remove(script_path)

            # Check for success
            if "BLENDER_RENDER_SUCCESS" in stdout_str:
                success_msg = [line for line in stdout_str.split('\n') if "BLENDER_RENDER_SUCCESS" in line][0]
                perf_tracker.end_timer("blender_render", start_time)
                return True, success_msg.replace("BLENDER_RENDER_SUCCESS: ", "")
            else:
                logger.error(f"Blender render error: {stderr_str}")
                perf_tracker.end_timer("blender_render", start_time)
                return False, f"Error rendering scene: {stderr_str}"

        except Exception as e:
            try:
                os.remove(script_path)
            except:
                pass

            logger.error(f"Error in render_scene: {e}")
            perf_tracker.end_timer("blender_render", start_time)
            return False, f"Error rendering scene: {e}"

    async def apply_operation(self, operation: str, object_name: str = None,
                              params: Dict[str, Any] = None) -> Tuple[bool, str]:
        """
        Apply an operation to an object or the scene.

        Args:
            operation: Operation name (e.g., 'translate', 'rotate', 'scale', 'duplicate', 'delete')
            object_name: Name of the object to operate on (None for scene operations)
            params: Operation parameters

        Returns:
            Tuple of (success: bool, message: str)
        """
        if not self.has_blender:
            return False, "Blender not found. Please set the blender_path in config or install Blender."

        # Check if blend file exists
        blend_file = config_manager.get("blender_output_file", "")
        if not blend_file or not os.path.exists(blend_file):
            return False, "No Blender file to modify. Create objects first."

        perf_tracker.increment_counter("blender_operations")
        start_time = perf_tracker.start_timer("blender_operation")

        params = params or {}

        # Create temporary Python script
        script_fd, script_path = tempfile.mkstemp(suffix=".py", prefix="blender_op_")
        try:
            # Start script with common imports
            script_content = """
import bpy
import math

# Helper function to find an object by name
def get_object(name):
    if name in bpy.data.objects:
        return bpy.data.objects[name]
    return None

"""

            # Add operation-specific code
            if operation == "translate" or operation == "move":
                x = params.get("x", 0)
                y = params.get("y", 0)
                z = params.get("z", 0)

                script_content += f"""
# Translate operation
obj = get_object('{object_name}')
if obj:
    obj.location.x += {x}
    obj.location.y += {y}
    obj.location.z += {z}
    print(f"BLENDER_SUCCESS: Moved {{obj.name}} to {{obj.location}}")
else:
    print(f"ERROR: Object '{object_name}' not found")
"""

            elif operation == "rotate":
                x = params.get("x", 0)
                y = params.get("y", 0)
                z = params.get("z", 0)
                is_degrees = params.get("degrees", True)

                if is_degrees:
                    # Convert to radians for Blender
                    script_content += f"""
# Rotate operation (from degrees)
obj = get_object('{object_name}')
if obj:
    obj.rotation_euler.x += math.radians({x})
    obj.rotation_euler.y += math.radians({y})
    obj.rotation_euler.z += math.radians({z})
    print(f"BLENDER_SUCCESS: Rotated {{obj.name}} to {{[math.degrees(r) for r in obj.rotation_euler]}} degrees")
else:
    print(f"ERROR: Object '{object_name}' not found")
"""
                else:
                    # Already in radians
                    script_content += f"""
# Rotate operation (radians)
obj = get_object('{object_name}')
if obj:
    obj.rotation_euler.x += {x}
    obj.rotation_euler.y += {y}
    obj.rotation_euler.z += {z}
    print(f"BLENDER_SUCCESS: Rotated {{obj.name}} to {{obj.rotation_euler}}")
else:
    print(f"ERROR: Object '{object_name}' not found")
"""

            elif operation == "scale":
                x = params.get("x", 1)
                y = params.get("y", 1)
                z = params.get("z", 1)
                uniform = params.get("uniform", False)

                if uniform and "factor" in params:
                    factor = params.get("factor", 1)
                    script_content += f"""
# Uniform scale operation
obj = get_object('{object_name}')
if obj:
    obj.scale *= {factor}
    print(f"BLENDER_SUCCESS: Scaled {{obj.name}} uniformly by {factor} to {{obj.scale}}")
else:
    print(f"ERROR: Object '{object_name}' not found")
"""
                else:
                    script_content += f"""
# Non-uniform scale operation
obj = get_object('{object_name}')
if obj:
    obj.scale.x *= {x}
    obj.scale.y *= {y}
    obj.scale.z *= {z}
    print(f"BLENDER_SUCCESS: Scaled {{obj.name}} to {{obj.scale}}")
else:
    print(f"ERROR: Object '{object_name}' not found")
"""

            elif operation == "duplicate":
                new_name = params.get("new_name", f"{object_name}_copy")
                offset_x = params.get("offset_x", 1)
                offset_y = params.get("offset_y", 0)
                offset_z = params.get("offset_z", 0)

                script_content += f"""
# Duplicate operation
obj = get_object('{object_name}')
if obj:
    # Select the object and make it active
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    # Duplicate
    bpy.ops.object.duplicate()

    # Rename the duplicate
    new_obj = bpy.context.active_object
    new_obj.name = '{new_name}'

    # Move the duplicate
    new_obj.location.x += {offset_x}
    new_obj.location.y += {offset_y}
    new_obj.location.z += {offset_z}

    print(f"BLENDER_SUCCESS: Duplicated {{obj.name}} to create {{new_obj.name}} at {{new_obj.location}}")
else:
    print(f"ERROR: Object '{object_name}' not found")
"""

            elif operation == "delete":
                script_content += f"""
# Delete operation
obj = get_object('{object_name}')
if obj:
    obj_name = obj.name
    bpy.data.objects.remove(obj, do_unlink=True)
    print(f"BLENDER_SUCCESS: Deleted {{obj_name}}")
else:
    print(f"ERROR: Object '{object_name}' not found")
"""

            elif operation == "join" or operation == "merge":
                objects_to_join = params.get("objects", [])
                target = params.get("target", object_name)

                # Convert the list to a string for script
                objects_str = ", ".join([f"'{obj}'" for obj in objects_to_join])

                script_content += f"""
# Join/Merge operation
target = get_object('{target}')
if not target:
    print(f"ERROR: Target object '{target}' not found")
else:
    objects_to_join = []
    for obj_name in [{objects_str}]:
        obj = get_object(obj_name)
        if obj and obj != target:
            objects_to_join.append(obj)

    if objects_to_join:
        # Select objects
        bpy.ops.object.select_all(action='DESELECT')
        for obj in objects_to_join:
            obj.select_set(True)

        # Set target as active
        target.select_set(True)
        bpy.context.view_layer.objects.active = target

        # Join
        bpy.ops.object.join()
        print(f"BLENDER_SUCCESS: Joined {{len(objects_to_join)}} objects into {{target.name}}")
    else:
        print("ERROR: No valid objects to join")
"""

            elif operation == "add_modifier":
                modifier_type = params.get("type", "SUBSURF")
                modifier_params = params.get("modifier_params", {})

                script_content += f"""
# Add modifier operation
obj = get_object('{object_name}')
if obj:
    mod = obj.modifiers.new(name='{modifier_type}', type='{modifier_type}')

"""
                # Add parameters dynamically
                for param, value in modifier_params.items():
                    script_content += f"    mod.{param} = {value}\n"

                script_content += f"""
    print(f"BLENDER_SUCCESS: Added {{mod.type}} modifier to {{obj.name}}")
else:
    print(f"ERROR: Object '{object_name}' not found")
"""

            elif operation == "add_constraint":
                constraint_type = params.get("type", "COPY_LOCATION")
                target_obj = params.get("target", "")
                constraint_params = params.get("constraint_params", {})

                script_content += f"""
# Add constraint operation
obj = get_object('{object_name}')
if obj:
    constraint = obj.constraints.new('{constraint_type}')
"""
                if target_obj:
                    script_content += f"""
    target = get_object('{target_obj}')
    if target:
        constraint.target = target
"""

                # Add parameters dynamically
                for param, value in constraint_params.items():
                    script_content += f"    constraint.{param} = {value}\n"

                script_content += f"""
    print(f"BLENDER_SUCCESS: Added {{constraint.type}} constraint to {{obj.name}}")
else:
    print(f"ERROR: Object '{object_name}' not found")
"""

            else:
                # Unknown operation
                perf_tracker.end_timer("blender_operation", start_time)
                return False, f"Unknown operation: {operation}"

            # Add save command at the end
            script_content += """
# Save the file
bpy.ops.wm.save_mainfile()
"""

            # Write the script to the temporary file
            async with aiofiles.open(script_path, 'w') as f:
                await f.write(script_content)

            # Execute Blender with the script
            process = await asyncio.create_subprocess_exec(
                self.blender_path, "--background", blend_file, "--python", script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()
            stdout_str = stdout.decode(errors='replace')
            stderr_str = stderr.decode(errors='replace')

            # Clean up the temporary script
            os.remove(script_path)

            # Check for success
            if "BLENDER_SUCCESS" in stdout_str:
                success_msg = [line for line in stdout_str.split('\n') if "BLENDER_SUCCESS" in line][0]
                perf_tracker.end_timer("blender_operation", start_time)
                return True, success_msg.replace("BLENDER_SUCCESS: ", "")
            else:
                error_msg = stderr_str
                # Check if there's a more specific error message in stdout
                error_lines = [line for line in stdout_str.split('\n') if "ERROR:" in line]
                if error_lines:
                    error_msg = error_lines[0].replace("ERROR: ", "")

                logger.error(f"Blender operation error: {error_msg}")
                perf_tracker.end_timer("blender_operation", start_time)
                return False, f"Error applying {operation}: {error_msg}"

        except Exception as e:
            try:
                os.remove(script_path)
            except:
                pass

            logger.error(f"Error in apply_operation: {e}")
            perf_tracker.end_timer("blender_operation", start_time)
            return False, f"Error applying operation: {e}"