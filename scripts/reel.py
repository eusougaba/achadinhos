"""Gera um vídeo vertical (Reel) a partir da imagem do story, sem metadados.

Uso: python3 scripts/reel.py entrada.jpg saida.mp4
Zoom lento de 9 segundos, 1080x1920, sem áudio de terceiros e sem nenhum metadado.
(Vídeos de terceiros não são baixados nem reaproveitados; só usamos imagens e textos próprios.)
"""
import shutil, subprocess, sys
from pathlib import Path


def gerar_reel(imagem: Path, destino: Path, segundos: int = 9) -> bool:
    if not shutil.which("ffmpeg"):
        return False
    destino.parent.mkdir(parents=True, exist_ok=True)
    quadros = segundos * 30
    filtro = (f"scale=2160:3840,zoompan=z='min(1+0.0007*on,1.18)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
              f":d={quadros}:s=1080x1920:fps=30,format=yuv420p")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(imagem),
           "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
           "-vf", filtro, "-t", str(segundos), "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
           "-c:a", "aac", "-b:a", "64k", "-shortest",
           "-map_metadata", "-1", "-fflags", "+bitexact", "-flags:v", "+bitexact", "-movflags", "+faststart",
           str(destino)]
    return subprocess.run(cmd).returncode == 0


if __name__ == "__main__":
    print("ok" if gerar_reel(Path(sys.argv[1]), Path(sys.argv[2])) else "falhou")
