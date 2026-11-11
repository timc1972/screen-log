# Screen Log: a personal movie and TV website

This is a **read-only**, mobile-friendly website for Trakt account **@kfg72**. It starts from a **sanitized Nuvio history snapshot** (57 movies, 20 series, and 431 watched episodes), then can refresh from **Trakt** every morning once published.

The site does not contain Nuvio login data, add-on URLs, playback tokens, or private profile identifiers. The original Nuvio backup is deliberately **not included**.

## 1. Try the website privately

Open `ScreenLog_Preview.html` (alongside this README) in Chrome or Edge. This standalone preview works without a web server. You can search movies, browse series, inspect episode details, and view the watch timeline.

Alternatively, open `site/index.html` after extracting the full ZIP. Leave `site/data.js`, `site/app.js`, and `site/styles.css` together.

**Important:** This first preview reflects the Nuvio backup created on November 11, 2026, not a live Trakt API read. It may exclude watches after the backup. Poster images need an internet connection and may not be available for every title.

## 2. Publish it using GitHub Pages

The simplest no-monthly-hosting-cost deployment is GitHub Pages. The published site will be **public to anyone with the link**. Review the preview first, including titles and watched dates, before publishing.

1. At github.com, create a **new repository** called `screen-log`. For GitHub Free hosting, choose **Public**. Do not add a template, README, or license at creation.
2. Extract this ZIP. Upload **the contents of the `ScreenLogSite` folder**, keeping `site/`, `scripts/`, and `.github/workflows/publish.yml` in their original paths. GitHub Desktop can make this easier if browser upload doesn't preserve folders.
3. In the repository, open **Settings → Pages**. Set **Build and deployment → Source: GitHub Actions**.
4. In **Settings → Secrets and variables → Actions → New repository secret**, set name `TRAKT_CLIENT_ID` and value to the **Client ID** from the Trakt developer app you already created (not the Client Secret, not a password, not an OAuth token). Don't paste secrets into your repository or chat.
5. In **Actions**, open **Sync and publish Screen Log** and choose **Run workflow**. A normal push to `main` should also trigger it.
6. After deployment, go to Settings → Pages to get the exact live URL. GitHub Pages typically follows `https://YOUR_GITHUB_USERNAME.github.io/screen-log/`.

If you don't add the secret, the site can still publish the **snapshot**, but it will **not live-sync**. If Trakt's user history is private or otherwise inaccessible, the workflow will fail safely and leave your previous published version unchanged. You can keep the history public in Trakt for a read-only sync, or modify the integration later to use a privately stored OAuth token.

## 3. How updates work

```
Nuvio watching → Trakt history → GitHub Actions → Screen Log website
```

The GitHub workflow runs on pushes, manually, and once daily (10:33 UTC). It queries the Trakt API with your GitHub Action secret, fetches all pages of movie and episode history, creates a small public snapshot, caches Trakt poster images locally, and publishes the website.

The script preserves the history dates Trakt returns, deduplicates movies and episodes in the collection view, and refuses to replace existing data if the new response unexpectedly loses most of the records. Trakt's API supports public history lookups with an API key, but availability and returned fields can vary with profile privacy and API changes.

The initial preview uses Nuvio/Cinemeta poster URLs as a best-effort visual reference. For Trakt-provided posters, `scripts/sync_trakt.py` downloads them to `site/posters/` in the build rather than hotlinking them, consistent with Trakt's current image policy. Missing artwork is shown with a designed placeholder.

## 4. What this version does and doesn't do

**Included:** movie grid, series grid, episode-by-episode detail panel, recent watches, history timeline, sorting, filtering, search, a calendar-style viewing chart, share-link control when published, and responsive layout.

**Not yet included:** personal ratings, favorites, written reviews, streaming availability, a login/admin interface, or direct ChatGPT editing. Those need design choices and sometimes extra authorization. The website currently shows what you **watched**, not what you **liked**.

**Note on dates:** Nuvio timestamps may represent when viewing was recorded or imported, not necessarily the actual calendar date the movie was first watched. Imported episodes may have clustered dates.

## 5. Rebuild the snapshot from a future Nuvio backup (optional)

This is unnecessary after Trakt sync is working. If needed:

```
python scripts/build_seed.py /path/to/new-nuvio-backup.json
```

Do not commit or publish the original Nuvio backup. The script outputs only the public viewing fields, not passwords or add-on configuration. When Nuvio lacks a series name, the import uses an existing reference file if available, plus corrections for King of the Hill, Slow Horses, and Lucky. For best accuracy, prefer Trakt's verified series titles after live synchronization.

## Credits and privacy

Screen Log uses Trakt but is not endorsed or certified by Trakt. Trakt API use: https://developer.trakt.tv/docs/api-use-policy.

Publishing the site discloses the list of watched titles and their viewing dates in public JSON/JavaScript. It does **not** require publishing the original Nuvio backup. GitHub repository secrets are available to the GitHub Actions environment and must not be printed in logs.
