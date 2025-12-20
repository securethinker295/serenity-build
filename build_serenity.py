#!/usr/bin/env python3
"""
SerenityOS Builder Script
Clones, builds, and packages SerenityOS GRUB UEFI disk image for x86_64
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
import gzip
from datetime import datetime

class SerenityBuilder:
    def __init__(self):
        self.work_dir = Path.cwd()
        self.serenity_dir = self.work_dir / "serenity"
        self.build_dir = self.serenity_dir / "Build" / "x86_64"
        self.arch = "x86_64"
        self.toolchain = "GNU"
        
    def log(self, message):
        """Print timestamped log message"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}", flush=True)
        
    def run_command(self, cmd, cwd=None, env=None):
        """Run a shell command and handle errors"""
        self.log(f"Running: {cmd}")
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd or self.work_dir,
                env=env,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            print(result.stdout)
            return result
        except subprocess.CalledProcessError as e:
            self.log(f"ERROR: Command failed with exit code {e.returncode}")
            print(e.stdout)
            sys.exit(1)
            
    def clone_repository(self):
        """Clone SerenityOS repository"""
        self.log("Cloning SerenityOS repository...")
        if self.serenity_dir.exists():
            self.log("Repository already exists, skipping clone")
            return
            
        self.run_command(
            "git clone --depth 1 https://github.com/SerenityOS/serenity.git"
        )
        self.log("Repository cloned successfully")
        
    def install_dependencies(self):
        """Install required system dependencies"""
        self.log("Installing system dependencies...")
        
        deps = [
            "build-essential", "cmake", "curl", "libmpfr-dev", "libmpc-dev",
            "libgmp-dev", "e2fsprogs", "ninja-build", "qemu-system-gui",
            "qemu-system-x86", "qemu-utils", "ccache", "rsync", "unzip",
            "texinfo", "libssl-dev", "zlib1g-dev", "gcc-13", "g++-13"
        ]
        
        self.run_command("sudo apt-get update")
        self.run_command(f"sudo apt-get install -y {' '.join(deps)}")
        self.log("Dependencies installed successfully")
        
    def build_serenity(self):
        """Build SerenityOS"""
        self.log("Building SerenityOS...")
        
        env = os.environ.copy()
        env["SERENITY_ARCH"] = self.arch
        env["SERENITY_TOOLCHAIN"] = self.toolchain
        
        self.run_command(
            "./Meta/serenity.sh build",
            cwd=self.serenity_dir,
            env=env
        )
        self.log("SerenityOS build completed successfully")
        
    def build_grub_uefi_image(self):
        """Build GRUB UEFI disk image"""
        self.log("Building GRUB UEFI disk image...")
        
        if not self.build_dir.exists():
            self.log(f"ERROR: Build directory not found: {self.build_dir}")
            sys.exit(1)
            
        self.run_command("ninja grub-uefi-image", cwd=self.build_dir)
        self.log("GRUB UEFI image built successfully")
        
    def compress_image(self):
        """Compress the disk image"""
        self.log("Compressing disk image...")
        
        source_image = self.build_dir / "grub_uefi_disk_image"
        output_name = f"serenity-x86_64-grub-uefi-{datetime.now().strftime('%Y%m%d')}.img"
        output_image = self.work_dir / output_name
        compressed_image = self.work_dir / f"{output_name}.gz"
        
        if not source_image.exists():
            self.log(f"ERROR: Disk image not found: {source_image}")
            sys.exit(1)
            
        # Copy image to output directory
        self.log(f"Copying image to {output_image}")
        shutil.copy2(source_image, output_image)
        
        # Compress with gzip
        self.log(f"Compressing to {compressed_image}")
        with open(output_image, 'rb') as f_in:
            with gzip.open(compressed_image, 'wb', compresslevel=9) as f_out:
                shutil.copyfileobj(f_in, f_out)
                
        # Remove uncompressed image
        output_image.unlink()
        
        # Get file sizes
        compressed_size = compressed_image.stat().st_size / (1024 * 1024)
        self.log(f"Compressed image size: {compressed_size:.2f} MB")
        self.log(f"Output file: {compressed_image}")
        
        return compressed_image
        
    def create_artifact_info(self, image_path):
        """Create info file with build details"""
        info_file = self.work_dir / "build-info.txt"
        
        with open(info_file, 'w') as f:
            f.write(f"SerenityOS Build Information\n")
            f.write(f"{'=' * 50}\n")
            f.write(f"Build Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Architecture: {self.arch}\n")
            f.write(f"Toolchain: {self.toolchain}\n")
            f.write(f"Bootloader: GRUB UEFI\n")
            f.write(f"Image File: {image_path.name}\n")
            f.write(f"Image Size: {image_path.stat().st_size / (1024 * 1024):.2f} MB\n")
            f.write(f"\nUsage Instructions:\n")
            f.write(f"1. Extract: gunzip {image_path.name}\n")
            f.write(f"2. Write to USB: sudo dd if={image_path.stem} of=/dev/sdX bs=4M status=progress\n")
            f.write(f"3. Or use with VirtualBox/VMware\n")
            
        self.log(f"Created build info file: {info_file}")
        
    def run(self):
        """Main build process"""
        try:
            self.log("=" * 60)
            self.log("SerenityOS Builder Starting")
            self.log("=" * 60)
            
            self.clone_repository()
            self.install_dependencies()
            self.build_serenity()
            self.build_grub_uefi_image()
            image_path = self.compress_image()
            self.create_artifact_info(image_path)
            
            self.log("=" * 60)
            self.log("Build completed successfully!")
            self.log(f"Artifact ready: {image_path}")
            self.log("=" * 60)
            
        except Exception as e:
            self.log(f"FATAL ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    builder = SerenityBuilder()
    builder.run()
