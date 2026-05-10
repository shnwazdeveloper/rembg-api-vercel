# shnwazdev-rembgapi

Serverless background removal API powered by [`danielgatis/rembg`](https://github.com/danielgatis/rembg).

The API is built for Vercel Python Functions and defaults to the lightweight `u2netp` model so cold starts and model downloads stay practical for serverless hosting.

## Live

- Website: https://shnwazdev-rembgapi.vercel.app
- Docs: https://shnwazdev-rembgapi.vercel.app/docs/
- Model metadata: https://shnwazdev-rembgapi.vercel.app/model

## Endpoints

- `GET /api` - usage and endpoint metadata
- `GET /api/health` - health check
- `GET /model` - model metadata and supported options
- `GET /api/model` - model metadata and supported options
- `POST /api/remove` - remove an image background
- `GET /api/remove?url=https://example.com/input.jpg` - remove a background from a remote image URL

## Upload an image

```bash
curl -s -F file=@input.jpg https://shnwazdev-rembgapi.vercel.app/api/remove -o output.png
```

## Send a base64 image

```bash
curl -s \
  -H "Content-Type: application/json" \
  -d '{"image_base64":"data:image/png;base64,...."}' \
  https://shnwazdev-rembgapi.vercel.app/api/remove \
  -o output.png
```

## Send an image URL

```bash
curl -s \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/input.jpg"}' \
  https://shnwazdev-rembgapi.vercel.app/api/remove \
  -o output.png
```

For `GET /api/remove?url=...`, URL-encode the image URL if it contains `?`, `&`, spaces, or other special characters. The URL must be public and must return an `image/*` content type.

## Send raw image bytes

```bash
curl -s \
  -H "Content-Type: image/png" \
  --data-binary @input.png \
  https://shnwazdev-rembgapi.vercel.app/api/remove \
  -o output.png
```

## Options

Pass these as multipart fields, JSON keys, form fields, or query parameters:

- `model`: `u2netp` or `silueta`
- `alpha_matting`: `true` or `false`
- `only_mask`: `true` or `false`
- `post_process_mask`: `true` or `false`

## Model metadata

```bash
curl -s https://shnwazdev-rembgapi.vercel.app/model
```

This returns the default model, allowed models, model descriptions, and supported processing options.

## Environment variables

- `REMBG_MODEL`: default model, defaults to `u2netp`
- `ALLOWED_MODELS`: comma-separated allowed models, defaults to `u2netp,silueta`
- `MAX_IMAGE_BYTES`: optional app-side max input image bytes; defaults to `0` which disables the app limit
- `REQUEST_TIMEOUT_SECONDS`: remote image download timeout, defaults to `15`

Models are cached in `/tmp/rembg-models` during warm function reuse.

## Deploy

```bash
npx vercel@latest
npx vercel@latest --prod
```

## License

MIT
