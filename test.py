from diffusers import StableDiffusionXLPipeline
import torch, PIL.Image as Image

pipe = StableDiffusionXLPipeline.from_pretrained(
    "stabilityai/stable-diffusion-xl-base-1.0", torch_dtype=torch.float16
).to("cuda")

prompt = ("photorealistic portrait of an original person, friendly expression, "
          "studio lighting, neutral background, detailed skin")
img = pipe(prompt=prompt, guidance_scale=7.0, num_inference_steps=30, height=768, width=512).images[0]
img.save("avatar_base.png")