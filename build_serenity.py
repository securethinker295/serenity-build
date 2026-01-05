#!/usr/bin/env python3
"""
SerenityOS Builder Script (Fixed Version)
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
        if os.environ.get('CI'):
            self.log("Running in CI environment - skipping dependency installation")
            self.log("Dependencies should be installed by GitHub Actions workflow")
            return
        
        deps = [
            "build-essential", "cmake", "curl", "libmpfr-dev", "libmpc-dev",
            "libgmp-dev", "e2fsprogs", "ninja-build", "qemu-system-gui",
            "qemu-system-x86", "qemu-utils", "ccache", "rsync", "unzip",
            "texinfo", "libssl-dev", "zlib1g-dev",
            "gcc-14", "g++-14",  # Fixed: Changed from gcc-13 to gcc-14 (required)
            "parted", "grub-efi-amd64-bin", "grub2-common"  # Added: Required for GRUB image creation
        ]
        
        self.log("Updating package lists...")
        self.run_command("sudo apt-get update")
        
        self.log(f"Installing {len(deps)} packages...")
        self.run_command(f"sudo apt-get install -y {' '.join(deps)}")
        
        # Verify GCC 14 is installed
        self.log("Verifying GCC 14 installation...")
        try:
            result = subprocess.run(
                "gcc-14 --version",
                shell=True,
                capture_output=True,
                text=True,
                check=True
            )
            self.log(f"GCC 14 verified: {result.stdout.splitlines()[0]}")
        except subprocess.CalledProcessError:
            self.log("WARNING: GCC 14 not found. SerenityOS requires GCC 14 or Clang 17+")
            self.log("You may need to install from ubuntu-toolchain-r/test PPA")
            response = input("Continue anyway? (y/n): ")
            if response.lower() != 'y':
                sys.exit(1)
        
        self.log("Dependencies installed successfully")
        
    def build_toolchain(self):
        """Build SerenityOS toolchain if needed"""
        self.log("Building/updating SerenityOS toolchain...")
        self.log("This may take a while on first run...")
        
        env = os.environ.copy()
        env["SERENITY_ARCH"] = self.arch
        env["SERENITY_TOOLCHAIN"] = self.toolchain
        
        # The serenity.sh script will automatically build the toolchain if needed
        self.run_command(
            f"./Toolchain/BuildIt.sh",
            cwd=self.serenity_dir,
            env=env
        )
        self.log("Toolchain ready")
        
    def build_serenity(self):
        """Build SerenityOS"""
        self.log("Building SerenityOS...")
        
        env = os.environ.copy()
        env["SERENITY_ARCH"] = self.arch
        env["SERENITY_TOOLCHAIN"] = self.toolchain
        
        # Fixed: Changed from 'build' to 'image' to ensure ninja install runs
        # This is required before building the GRUB image
        self.log(f"Running: Meta/serenity.sh image {self.arch}")
        self.run_command(
            f"./Meta/serenity.sh image {self.arch}",
            cwd=self.serenity_dir,
            env=env
        )
        self.log("SerenityOS build and install completed successfully")
        
    def build_grub_uefi_image(self):
        """Build GRUB UEFI disk image"""
        self.log("Building GRUB UEFI disk image...")
        
        if not self.build_dir.exists():
            self.log(f"ERROR: Build directory not found: {self.build_dir}")
            sys.exit(1)
        
        # Verify grub_uefi_disk_image doesn't already exist
        grub_image = self.build_dir / "grub_uefi_disk_image"
        if grub_image.exists():
            self.log("Removing existing GRUB UEFI image...")
            grub_image.unlink()
            
        self.run_command("ninja grub-uefi-image", cwd=self.build_dir)
        
        # Verify the image was created
        if not grub_image.exists():
            self.log("ERROR: GRUB UEFI image was not created!")
            sys.exit(1)
            
        image_size = grub_image.stat().st_size / (1024 * 1024)
        self.log(f"GRUB UEFI image built successfully ({image_size:.2f} MB)")
        
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
        
        original_size = source_image.stat().st_size / (1024 * 1024)
        self.log(f"Original image size: {original_size:.2f} MB")
            
        # Copy image to output directory
        self.log(f"Copying image to {output_image}")
        shutil.copy2(source_image, output_image)
        
        # Compress with gzip
        self.log(f"Compressing to {compressed_image} (this may take a moment)...")
        with open(output_image, 'rb') as f_in:
            with gzip.open(compressed_image, 'wb', compresslevel=9) as f_out:
                shutil.copyfileobj(f_in, f_out)
                
        # Remove uncompressed image
        output_image.unlink()
        
        # Get file sizes
        compressed_size = compressed_image.stat().st_size / (1024 * 1024)
        compression_ratio = (1 - compressed_size / original_size) * 100
        self.log(f"Compressed image size: {compressed_size:.2f} MB ({compression_ratio:.1f}% reduction)")
        self.log(f"Output file: {compressed_image}")
        
        return compressed_image
        
    def create_artifact_info(self, image_path):
        """Create info file with build details"""
        info_file = self.work_dir / "build-info.txt"
        
        with open(info_file, 'w') as f:
            f.write(f"SerenityOS Build Information\n")
            f.write(f"{'=' * 60}\n")
            f.write(f"Build Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Architecture: {self.arch}\n")
            f.write(f"Toolchain: {self.toolchain}\n")
            f.write(f"Bootloader: GRUB UEFI\n")
            f.write(f"Image File: {image_path.name}\n")
            f.write(f"Image Size: {image_path.stat().st_size / (1024 * 1024):.2f} MB\n")
            f.write(f"\n{'=' * 60}\n")
            f.write(f"Usage Instructions:\n")
            f.write(f"{'=' * 60}\n\n")
            f.write(f"1. Extract the compressed image:\n")
            f.write(f"   gunzip {image_path.name}\n\n")
            f.write(f"2. Write to USB drive (Linux):\n")
            f.write(f"   sudo dd if={image_path.stem} of=/dev/sdX bs=64M status=progress && sync\n")
            f.write(f"   (Replace /dev/sdX with your USB device)\n\n")
            f.write(f"3. Boot with QEMU (macOS example):\n")
            f.write(f"   qemu-system-x86_64 -m 2G \\\n")
            f.write(f"     -drive if=pflash,format=raw,readonly=on,file=/opt/homebrew/share/qemu/edk2-x86_64-code.fd \\\n")
            f.write(f"     -drive file={image_path.stem},format=raw\n\n")
            f.write(f"4. Or use with VirtualBox/VMware (configure as UEFI boot)\n\n")
            f.write(f"{'=' * 60}\n")
            f.write(f"Hardware Requirements:\n")
            f.write(f"{'=' * 60}\n")
            f.write(f"- Minimum 256 MB RAM (2GB+ recommended)\n")
            f.write(f"- x86_64 CPU\n")
            f.write(f"- >= 2 GB storage (SATA/NVMe/USB)\n")
            f.write(f"- UEFI firmware support\n\n")
            f.write(f"{'=' * 60}\n")
            f.write(f"Default Credentials:\n")
            f.write(f"{'=' * 60}\n")
            f.write(f"Username: anon\n")
            f.write(f"Password: foo\n")
            f.write(f"(anon user can become root without password by default)\n")
            
        self.log(f"Created build info file: {info_file}")
        
    def run(self):
        """Main build process"""
        try:
            self.log("=" * 60)
            self.log("SerenityOS Builder Starting")
            self.log("=" * 60)
            
            self.clone_repository()
            self.install_dependencies()
            self.build_toolchain()
            self.build_serenity()
            self.build_grub_uefi_image()
            image_path = self.compress_image()
            self.create_artifact_info(image_path)
            
            self.log("=" * 60)
            self.log("Build completed successfully!")
            self.log(f"Artifact ready: {image_path}")
            self.log(f"See build-info.txt for usage instructions")
            self.log("=" * 60)
            
        except KeyboardInterrupt:
            self.log("\nBuild interrupted by user")
            sys.exit(1)
        except Exception as e:
            self.log(f"FATAL ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    builder = SerenityBuilder()
    builder.run()