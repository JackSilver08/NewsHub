# Integrated thumbnail service

This is the website-owned subset of AI Image Factory. It contains the FastAPI
job pipeline, Creative Director, layout renderer, and ComfyUI workflows used by
the admin thumbnail button.

Run it from the website root:

```powershell
npm run image-service
```

ComfyUI remains a separate local process at `http://127.0.0.1:8188`. Its model
files are intentionally not stored in this Git repository: the current model
set is over 9 GB and exceeds GitHub's file limits. The expected Z-Image workflow
uses these ComfyUI model filenames:

- `z_image_turbo_int8_convrot.safetensors`
- `qwen_3_4b_fp4_mixed.safetensors`
- `ae.safetensors`

You may move the original `Gen Img Tool` directory elsewhere and continue using
its ComfyUI installation. Only ComfyUI and its models need to remain outside;
the website's API integration no longer imports code from that directory.
