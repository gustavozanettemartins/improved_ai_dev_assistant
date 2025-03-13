#!/usr/bin/env python3

import os
import json
from typing import List, Dict, Any
from colorama import Fore, Style

from config.config_manager import config_manager, logger
from core.performance import perf_tracker
from blender.blender_handler import BlenderHandler


class BlenderCommands:
    """Handles Blender-related commands in the CLI."""

    def __init__(self, blender_handler: BlenderHandler = None):
        """
        Initialize the BlenderCommands handler.

        Args:
            blender_handler: Initialized BlenderHandler instance or None to create a new one
        """
        self.blender_handler = blender_handler or BlenderHandler()
        self.object_types = ["cube", "sphere", "plane", "cylinder", "cone", "torus"]
        self.operations = ["move", "rotate", "scale", "duplicate", "delete", "join",
                           "merge", "add_modifier", "add_constraint"]

        # Ensure Blender output directory exists
        self.output_dir = os.path.join(config_manager.get("working_dir"), "blender_output")
        os.makedirs(self.output_dir, exist_ok=True)

        # Set default blend file
        if not config_manager.get("blender_output_file"):
            config_manager.set("blender_output_file", os.path.join(self.output_dir, "scene.blend"))

        logger.info("BlenderCommands initialized")

    async def check_status(self, args: List[str] = None) -> str:
        """Check the Blender connection status."""
        success, message = await self.blender_handler.check_blender_connection()

        if success:
            return f"{Fore.RED}❌ {message}{Style.RESET_ALL}"

    async def create_object(self, args: List[str]) -> str:
        """Create a 3D object in Blender."""
        if not args:
            return f"Usage: :blender create <object_type> [name] [x y z] [size_x size_y size_z]\n" \
                   f"Available object types: {', '.join(self.object_types)}"

        obj_type = args[0].lower()
        if obj_type not in self.object_types:
            return f"{Fore.RED}Invalid object type: {obj_type}\n" \
                   f"Available types: {', '.join(self.object_types)}{Style.RESET_ALL}"

        # Parse optional parameters
        name = args[1] if len(args) > 1 else None

        # Parse location if provided
        location = None
        if len(args) > 4:  # At least x, y, z coordinates
            try:
                location = [float(args[2]), float(args[3]), float(args[4])]
            except ValueError:
                return f"{Fore.RED}Invalid coordinates. Use numbers for x, y, z position.{Style.RESET_ALL}"

        # Parse size if provided
        size = None
        if len(args) > 7:  # At least size_x, size_y, size_z
            try:
                size = [float(args[5]), float(args[6]), float(args[7])]
            except ValueError:
                return f"{Fore.RED}Invalid size. Use numbers for size_x, size_y, size_z.{Style.RESET_ALL}"

        # Create material (with defaults)
        material = {
            "color": [0.8, 0.8, 0.8, 1.0],
            "metallic": 0.0,
            "roughness": 0.5
        }

        # Execute the creation
        success, message = await self.blender_handler.create_object(
            obj_type=obj_type,
            name=name,
            location=location,
            size=size,
            material=material
        )

        if success:
            # Store the last created object name for potential further operations
            if "Created" in message and " at " in message:
                obj_name = message.split("Created ")[1].split(" at ")[0]
                config_manager.set("blender_last_object", obj_name)

            return f"{Fore.GREEN}✅ {message}{Style.RESET_ALL}"
        else:
            return f"{Fore.RED}❌ {message}{Style.RESET_ALL}"

    async def render_scene(self, args: List[str]) -> str:
        """Render the current Blender scene to an image file."""
        # Default output path
        output_path = os.path.join(self.output_dir, "render.png")
        width = 1920
        height = 1080
        samples = 128
        engine = "CYCLES"

        # Parse arguments
        if args:
            # Check if output path is provided
            if args[0].endswith((".png", ".jpg", ".jpeg", ".bmp")):
                output_path = args[0]
                if not os.path.isabs(output_path):
                    output_path = os.path.join(self.output_dir, output_path)
                args = args[1:]

            # Parse width and height if provided
            if len(args) >= 2:
                try:
                    width = int(args[0])
                    height = int(args[1])
                    args = args[2:]
                except ValueError:
                    return f"{Fore.RED}Invalid width/height. Use integers.{Style.RESET_ALL}"

            # Parse samples if provided
            if args and args[0].isdigit():
                samples = int(args[0])
                args = args[1:]

            # Parse engine if provided
            if args and args[0].upper() in ["CYCLES", "EEVEE"]:
                engine = args[0].upper()

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Execute the render
        success, message = await self.blender_handler.render_scene(
            output_path=output_path,
            width=width,
            height=height,
            samples=samples,
            engine=engine
        )

        if success:
            return f"{Fore.GREEN}✅ {message}{Style.RESET_ALL}"
        else:
            return f"{Fore.RED}❌ {message}{Style.RESET_ALL}"

    async def apply_operation(self, args: List[str]) -> str:
        """Apply an operation to a Blender object."""
        if len(args) < 2:
            return f"Usage: :blender <operation> <object_name> [parameters...]\n" \
                   f"Available operations: {', '.join(self.operations)}"

        operation = args[0].lower()
        object_name = args[1]

        # Use last created object if specified
        if object_name == "last":
            object_name = config_manager.get("blender_last_object", None)
            if not object_name:
                return f"{Fore.RED}No last object available. Create an object first.{Style.RESET_ALL}"

        params = {}

        # Parse operation-specific parameters
        if operation == "move" or operation == "translate":
            if len(args) < 5:
                return f"Usage: :blender move <object_name> <x> <y> <z>"

            try:
                params = {
                    "x": float(args[2]),
                    "y": float(args[3]),
                    "z": float(args[4])
                }
            except ValueError:
                return f"{Fore.RED}Invalid coordinates. Use numbers for x, y, z movement.{Style.RESET_ALL}"

        elif operation == "rotate":
            if len(args) < 5:
                return f"Usage: :blender rotate <object_name> <x_degrees> <y_degrees> <z_degrees> [radians|degrees]"

            try:
                params = {
                    "x": float(args[2]),
                    "y": float(args[3]),
                    "z": float(args[4])
                }

                # Check if using radians
                if len(args) > 5 and args[5].lower() == "radians":
                    params["degrees"] = False
                else:
                    params["degrees"] = True

            except ValueError:
                return f"{Fore.RED}Invalid rotation angles. Use numbers for x, y, z rotation.{Style.RESET_ALL}"

        elif operation == "scale":
            # Check for uniform scaling
            if len(args) == 3:
                try:
                    params = {
                        "uniform": True,
                        "factor": float(args[2])
                    }
                except ValueError:
                    return f"{Fore.RED}Invalid scale factor. Use a number.{Style.RESET_ALL}"
            elif len(args) >= 5:
                try:
                    params = {
                        "x": float(args[2]),
                        "y": float(args[3]),
                        "z": float(args[4])
                    }
                except ValueError:
                    return f"{Fore.RED}Invalid scale values. Use numbers for x, y, z scale.{Style.RESET_ALL}"
            else:
                return f"Usage: :blender scale <object_name> <factor>\n" \
                       f"   or: :blender scale <object_name> <x> <y> <z>"

        elif operation == "duplicate":
            new_name = f"{object_name}_copy"
            offset = [1, 0, 0]  # Default offset

            if len(args) > 2:
                new_name = args[2]

            if len(args) > 5:
                try:
                    offset = [float(args[3]), float(args[4]), float(args[5])]
                except ValueError:
                    return f"{Fore.RED}Invalid offset values. Use numbers for x, y, z offset.{Style.RESET_ALL}"

            params = {
                "new_name": new_name,
                "offset_x": offset[0],
                "offset_y": offset[1],
                "offset_z": offset[2]
            }

        elif operation == "delete":
            # No additional parameters needed
            pass

        elif operation == "join" or operation == "merge":
            if len(args) < 3:
                return f"Usage: :blender join <target_object> <object1> [object2] [object3] ..."

            params = {
                "target": object_name,
                "objects": args[2:]
            }

        elif operation == "add_modifier":
            if len(args) < 3:
                return f"Usage: :blender add_modifier <object_name> <modifier_type> [param1=value1 param2=value2...]"

            modifier_type = args[2].upper()
            modifier_params = {}

            # Parse modifier parameters
            for i in range(3, len(args)):
                if "=" in args[i]:
                    key, value = args[i].split("=", 1)

                    # Try to convert value to appropriate type
                    try:
                        if value.lower() == "true":
                            modifier_params[key] = True
                        elif value.lower() == "false":
                            modifier_params[key] = False
                        elif value.isdigit():
                            modifier_params[key] = int(value)
                        elif "." in value and all(p.isdigit() for p in value.split(".")):
                            modifier_params[key] = float(value)
                        else:
                            modifier_params[key] = value
                    except:
                        modifier_params[key] = value

            params = {
                "type": modifier_type,
                "modifier_params": modifier_params
            }

        else:
            return f"{Fore.RED}Unknown operation: {operation}\n" \
                   f"Available operations: {', '.join(self.operations)}{Style.RESET_ALL}"

        # Execute the operation
        success, message = await self.blender_handler.apply_operation(
            operation=operation,
            object_name=object_name,
            params=params
        )

        if success:
            # For duplicate operations, store the new object name
            if operation == "duplicate" and "create" in message.lower():
                for part in message.split():
                    if part.startswith(new_name):
                        config_manager.set("blender_last_object", part.strip())
                        break

            return f"{Fore.GREEN}✅ {message}{Style.RESET_ALL}"
        else:
            return f"{Fore.RED}❌ {message}{Style.RESET_ALL}"

    async def set_output_file(self, args: List[str]) -> str:
        """Set the Blender output file path."""
        if not args:
            current = config_manager.get("blender_output_file", "Not set")
            return f"Current Blender output file: {current}\n" \
                   f"Usage: :blender set_output <filename.blend>"

        filename = args[0]
        if not filename.endswith(".blend"):
            filename += ".blend"

        if not os.path.isabs(filename):
            filename = os.path.join(self.output_dir, filename)

        config_manager.set("blender_output_file", filename)
        return f"{Fore.GREEN}Blender output file set to: {filename}{Style.RESET_ALL}"

    async def handle_command(self, args: List[str]) -> str:
        """Main command handler for Blender commands."""
        if not args:
            return "Usage: :blender <subcommand> [options]\n" \
                   "Available subcommands: status, set_path, create, render, move, rotate, scale, duplicate, delete, set_output"

        subcommand = args[0].lower()

        if subcommand == "status":
            return await self.check_status(args[1:])
        elif subcommand == "set_path":
            return await self.set_blender_path(args[1:])
        elif subcommand == "create":
            return await self.create_object(args[1:])
        elif subcommand == "render":
            return await self.render_scene(args[1:])
        elif subcommand == "set_output" or subcommand == "output":
            return await self.set_output_file(args[1:])
        elif subcommand in self.operations:
            return await self.apply_operation([subcommand] + args[1:])
        else:
            return f"{Fore.RED}Unknown Blender subcommand: {subcommand}{Style.RESET_ALL}"

    async def set_blender_path(self, args: List[str]) -> str:
        """Set the path to the Blender executable."""
        if not args:
            return f"Usage: :blender set_path <path_to_blender_executable>"

        path = args[0]

        # Check if the path exists and is executable
        if not os.path.exists(path):
            return f"{Fore.RED}Error: File not found: {path}{Style.RESET_ALL}"

        if not os.access(path, os.X_OK):
            return f"{Fore.RED}Error: File is not executable: {path}{Style.RESET_ALL}"

        # Update the blender path
        self.blender_handler.blender_path = path
        self.blender_handler.has_blender = True

        # Save to config for persistence
        config_manager.set("blender_path", path)
        config_manager.save_config()

        return f"{Fore.GREEN}Blender path set to: {path}{Style.RESET_ALL}"