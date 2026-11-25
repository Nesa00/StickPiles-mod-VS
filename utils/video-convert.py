import argparse
import subprocess
from pathlib import Path


def mp4_to_webp(
    input_path: Path,
    output_path: Path | None = None,
    max_duration: float = 10.0,
    fps: int = 24,
    width: int = 720,
    quality: int = 75,
    loop: int = 0,
):
    if not input_path.exists():
        raise FileNotFoundError(f"Input video not found: {input_path}")

    dst = output_path if output_path else input_path.with_suffix(".webp")
    dst.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(input_path),
        "-t", str(max_duration),
        "-vf", f"fps={fps},scale={width}:-1:flags=lanczos",
        "-fps_mode", "cfr",       # Forces constant frame timing so VFR recordings don't become slideshows
        "-vcodec", "libwebp",
        "-lossless", "0",
        "-compression_level", "4",
        "-q:v", str(quality),
        "-loop", str(loop),
        "-preset", "default",
        "-an",
        str(dst),
    ]

    subprocess.run(cmd, check=True)
    print(f"Saved -> {dst}")


def main():
    parser = argparse.ArgumentParser(description="Convert an MP4 video to a smooth animated WebP.")
    parser.add_argument("-i", "--input", required=True, type=Path, help="Path to input MP4 file")
    parser.add_argument("-o", "--output", type=Path, default=None, help="Output WebP path")
    parser.add_argument("-t", "--duration", type=float, default=10.0, help="Max duration in seconds (default: 10.0)")
    parser.add_argument("--fps", type=int, default=24, help="Output framerate (default: 24)")
    parser.add_argument("-w", "--width", type=int, default=720, help="Output width in px (default: 720)")
    parser.add_argument("-q", "--quality", type=int, default=75, help="WebP quality 0-100 (default: 75)")

    args = parser.parse_args()
    mp4_to_webp(
        input_path=args.input,
        output_path=args.output,
        max_duration=args.duration,
        fps=args.fps,
        width=args.width,
        quality=args.quality,
    )


if __name__ == "__main__":
    main()