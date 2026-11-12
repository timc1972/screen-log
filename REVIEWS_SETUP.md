# ScreenLog personal reviews setup

ScreenLog is a public static GitHub Pages site. It **cannot safely write to GitHub
or maintain a private login** on its own. This feature therefore uses Firebase
Authentication (Google sign-in) and Cloud Firestore with security rules.

## User experience

- Visitors: open a movie or show and read **My Thoughts**, including an optional
  1–5 star rating. They never receive editing controls.
- Owner: use **Owner: Sign in** in the ScreenLog footer, choose your Google
  account, then open a movie or show and click **Write my review**.
- Write/edit on mobile, save, cancel, or delete. Reviews persist independently
  from Trakt/GitHub Actions. No private Google or GitHub token is stored in
  ScreenLog's public repository.
- This feature is **not active** until you complete the steps below.

## One-time activation steps

1. Visit https://console.firebase.google.com/ and **Create project**,
   e.g. "ScreenLog Reviews". Analytics is optional.
2. In **Project settings > Your apps**, register a **Web** app. Copy the
   Firebase web configuration values `apiKey`, `authDomain`, `projectId`,
   and `appId`. (These are browser configuration, not secret server keys.)
3. Edit `site/firebase-config.js` in this repository and insert those four
   values. Leave `ownerUid` blank for the first sign-in.
4. In Firebase **Authentication > Sign-in method**, enable **Google**.
   In **Authentication > Settings > Authorized domains**, add
   `timc1972.github.io` (hostname only, not a URL or path).
5. In **Firestore Database**, create a database in **Production mode**.
   Production mode blocks access until you publish rules. Do not use an
   unrestricted test mode for this public site.
6. Deploy the config update through GitHub Pages. Go to ScreenLog, use the
   **Owner: Sign in** button in the footer, and sign in with the Google account
   that should own the reviews. No editing access is given yet.
7. In **Firebase Authentication > Users**, find that newly signed-in account.
   Copy its **UID** (a Firebase-generated user identifier, not your email).
8. Paste that UID into BOTH:
   - `ownerUid` in `site/firebase-config.js`.
   - `REPLACE_WITH_YOUR_FIREBASE_AUTH_UID` in `firestore.rules`.
     In Firebase **Firestore Database > Rules**, paste the complete rules
     and click **Publish**. GitHub does not automatically deploy these rules.
9. Commit the updated `site/firebase-config.js` to `main`, and after the
   GitHub Pages deployment succeeds, reload the site and sign in.
10. Test saving and editing a review, then sign out and verify that the review
    is publicly readable but can't be edited. Also test in a private window.

## Security and ongoing costs

- Firebase Authentication is used only for sign-in. The **Firestore rules**
  enforce that the one allowed UID can create, edit, or delete reviews. The
  `ownerUid` value in browser JavaScript just hides controls; it is not
  the security boundary.
- No Firebase Admin service account JSON, GitHub personal access token,
  OAuth client secret, or private key should ever be committed to this repo.
  Firebase web configuration is designed to be public.
- Reviews are public: do not put passwords or private family information in
  them. Firestore public reads incur usage; check Firebase's current Spark
  plan quotas and billing terms. Back up important reviews independently.
- An ordinary user signing in with a different Google account cannot write
  because the UID won't match the Firestore rules.
- If editing says "Saving denied", verify the Firestore rules were **published**
  and `ownerUid` matches the account in Firebase Authentication.
- If sign-in fails, verify that Google provider is enabled and
  `timc1972.github.io` is an authorized domain. Browser popup blocking can
  also affect mobile sign-in; try opening ScreenLog in Chrome or Safari.
- No writeable admin login or Firebase project can be provisioned automatically
  with the GitHub connector. Those steps require the project owner's action.
