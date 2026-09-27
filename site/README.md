# Image MLX Lab website

The static site served at <https://houjun.dev/iml/>. English only. Plain HTML and one
stylesheet: no scripts, no third-party resources, no cookies. Modelled on the VoxStage site
(`/voxstage/`), with this project's own licence story: MIT code, default model under the Qwen
Research License (non-commercial).

`.htaccess` sets the security headers (a strict content security policy with scripts off),
caching, blocks internal files and serves `404.html`. `media/` and `.well-known/` have their
own `.htaccess`, because a subdirectory with its own rewrite rules does not inherit the parent's:
`media/` serves only images, `.well-known/` only `security.txt`.

## Deploy

Same host and method as the VoxStage and Mind Craft Fish sites: SFTP with an SSH key, the
details in their local, uncommitted deploy notes. Mirror this folder to the `iml` directory
beside `voxstage` — dry run first, then for real:

```sh
rsync -avzn --delete-after --exclude '.DS_Store' --exclude 'README.md' \
  -e "ssh -i <key> -p <port>" site/ <user>@<host>:<path>/iml/
```

Check the listed changes, drop `-n`, run again, then open the site and each page. Use
`--delete-after` (never bare `--delete`) so no page points at a file that is already gone
mid-upload. The dot folders (`.htaccess`, `.well-known/`) must be uploaded too.

After deploying, check:

- `https://houjun.dev/iml/` and each legal page load, with images;
- response headers include the `Content-Security-Policy` and `Strict-Transport-Security` lines;
- `https://houjun.dev/iml/README.md`, `/iml/.htaccess` and `/iml/media/x.txt` return 403;
- `https://houjun.dev/iml/.well-known/security.txt` is served as plain text;
- `https://houjun.dev/iml/nothing-here` shows the site's 404 page.

## Media

- `media/workbench-*.jpg`: English UI screenshots, taken with only purpose-generated demo images
  in the library (from `docs/images/ui-*-en-v1.png`).
- `media/demo-*.jpg`: before / mask / after panels of real workflow results on purpose-generated
  demo images (from `docs/images/showcase-*-en-v1.png`).
- `media/og-card-v1.jpg`: 1200×630 share image cut from the English overview.

All of them are listed in `docs/images/APPROVED.txt` and checked by
`scripts/check_public_release.py`. JPEGs are written without EXIF / Photoshop metadata.
Images are cached for 30 days: when one changes, give it a new name (`…-v2.jpg`) and update the
pages — never replace an approved file under the same name.
