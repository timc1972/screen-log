/* ScreenLog owner-only public reviews. No GitHub token or private key in browser. */
(() => {
  'use strict';
  const config = window.SCREENLOG_REVIEW_CONFIG || {};
  const enabled = ['apiKey', 'authDomain', 'projectId', 'appId']
    .every(key => typeof config[key] === 'string' && config[key].trim());
  const signinButton = document.getElementById('reviewOwnerAuth');
  const state = {
    ready: false, auth: null, db: null, sdk: null, user: null,
    item: null, kind: null, key: null, review: null, loading: false,
    editing: false, saving: false, sequence: 0
  };

  const makeKey = (kind, id) => {
    if (!['movie', 'show'].includes(kind)) return null;
    if (!/^(?:tt[0-9]+|trakt-[0-9]+)$/.test(String(id || ''))) return null;
    return kind + '_' + id;
  };
  const owner = () => Boolean(
    state.user && typeof config.ownerUid === 'string' &&
    config.ownerUid.length > 0 && state.user.uid === config.ownerUid
  );
  const node = (tag, className, text) => {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  };
  const reviewRoot = () => document.getElementById('personalReviewContent');
  const setFeedback = (message) => {
    const area = reviewRoot()?.querySelector('.review-feedback');
    if (area) area.textContent = message;
  };
  const button = (label, className, handler) => {
    const el = node('button', 'review-button ' + (className || ''), label);
    el.type = 'button';
    el.addEventListener('click', handler);
    return el;
  };

  function renderSignin() {
    if (!signinButton) return;
    signinButton.hidden = !enabled || !state.ready;
    signinButton.textContent = state.user ? 'Owner account: Sign out' : 'Owner: Sign in';
    signinButton.title = state.user && !owner()
      ? 'This account is not authorized to edit reviews.' : '';
  }

  function render() {
    const root = reviewRoot();
    if (!root || !state.key) return;
    root.replaceChildren();

    if (!enabled) {
      root.append(node('p', 'review-muted',
        'Personal reviews will appear here after review storage is connected.'));
      return;
    }
    if (!state.ready || state.loading) {
      root.append(node('p', 'review-muted', 'Loading review…'));
      return;
    }
    if (state.editing && owner()) {
      renderEditor(root);
      return;
    }
    const saved = state.review;
    if (saved && saved.body) {
      if (Number.isInteger(saved.stars) && saved.stars >= 1 && saved.stars <= 5) {
        const stars = node('div', 'review-stars',
          '★'.repeat(saved.stars) + '☆'.repeat(5 - saved.stars));
        stars.setAttribute('aria-label', saved.stars + ' out of 5 stars');
        root.append(stars);
      }
      root.append(node('p', 'review-body', saved.body));
    } else {
      root.append(node('p', 'review-muted', 'No personal review yet.'));
    }
    if (owner()) {
      root.append(button(saved ? 'Edit my review' : 'Write my review',
        'primary', () => { state.editing = true; render(); }));
    }
  }

  function renderEditor(root) {
    const existing = state.review || {};
    const form = node('form', 'review-editor');
    const textLabel = node('label', '', 'My review');
    const textarea = node('textarea');
    textarea.name = 'review';
    textarea.id = 'reviewText';
    textarea.maxLength = 3000;
    textarea.required = true;
    textarea.placeholder = 'What stood out? Would you watch it again?';
    textarea.value = existing.body || '';
    textLabel.htmlFor = textarea.id;
    textLabel.append(textarea);
    form.append(textLabel);

    const ratingLabel = node('label', '', 'My rating (optional)');
    const select = node('select');
    select.name = 'stars';
    select.id = 'reviewStars';
    ratingLabel.htmlFor = select.id;
    const choices = [
      ['0', 'No personal rating'], ['1', '★ 1 / 5'],
      ['2', '★★ 2 / 5'], ['3', '★★★ 3 / 5'],
      ['4', '★★★★ 4 / 5'], ['5', '★★★★★ 5 / 5']
    ];
    choices.forEach(([value, label]) => {
      const option = node('option', '', label);
      option.value = value;
      select.append(option);
    });
    select.value = String(existing.stars || 0);
    ratingLabel.append(select);
    form.append(ratingLabel);

    const feedback = node('p', 'review-feedback');
    feedback.setAttribute('role', 'status');
    form.append(feedback);
    const actions = node('div', 'review-actions');
    const save = button('Save review', 'primary', () => form.requestSubmit());
    const cancel = button('Cancel', '', () => {
      if (state.saving) return;
      state.editing = false; render();
    });
    actions.append(save, cancel);
    if (state.review) actions.append(button('Delete review', 'danger', removeReview));
    form.append(actions);
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (state.saving || !owner() || !state.key || !state.ready) return;
      const body = textarea.value.trim();
      if (!body || body.length > 3000) {
        feedback.textContent = 'Enter a review (up to 3,000 characters).';
        return;
      }
      const stars = Number(select.value);
      if (!Number.isInteger(stars) || stars < 0 || stars > 5) return;
      const key = state.key;
      state.saving = true;
      save.disabled = true;
      cancel.disabled = true;
      feedback.textContent = 'Saving…';
      try {
        const data = {
          body, stars, kind: state.kind,
          mediaId: String(state.item.id),
          title: String(state.item.title || '').slice(0, 150),
          updatedAt: state.sdk.serverTimestamp()
        };
        await state.sdk.setDoc(state.sdk.doc(state.db, 'reviews', key), data);
        if (state.key === key) {
          state.review = { ...data, updatedAt: new Date() };
          state.editing = false;
          render();
        }
      } catch (error) {
        feedback.textContent = error?.code === 'permission-denied'
          ? 'Saving denied. Check your owner UID and Firestore security rules.'
          : 'Unable to save. Check your connection and try again.';
      } finally {
        state.saving = false;
        save.disabled = false;
        cancel.disabled = false;
      }
    });
    root.append(form);
  }

  async function removeReview(event) {
    if (state.saving || !owner() || !state.review) return;
    if (!window.confirm('Delete your review for this title?')) return;
    const key = state.key;
    const clicked = event.currentTarget;
    clicked.disabled = true;
    state.saving = true;
    setFeedback('Deleting…');
    try {
      await state.sdk.deleteDoc(state.sdk.doc(state.db, 'reviews', key));
      if (state.key === key) {
        state.review = null; state.editing = false; render();
      }
    } catch (error) {
      setFeedback('Unable to delete this review. Please try again.');
    } finally {
      state.saving = false;
      clicked.disabled = false;
    }
  }

  async function load() {
    const key = state.key;
    const sequence = ++state.sequence;
    state.editing = false;
    state.review = null;
    state.loading = true;
    render();
    if (!state.ready || !key) return;
    try {
      const snapshot = await state.sdk.getDoc(state.sdk.doc(state.db, 'reviews', key));
      if (sequence !== state.sequence || key !== state.key) return;
      state.review = snapshot.exists() ? snapshot.data() : null;
    } catch (error) {
      if (sequence !== state.sequence) return;
      state.review = null;
      const root = reviewRoot();
      if (root) {
        root.replaceChildren(node('p', 'review-muted',
          'Personal review unavailable right now. Please try again later.'));
      }
      state.loading = false;
      return;
    }
    if (sequence === state.sequence) {
      state.loading = false;
      render();
    }
  }

  window.ScreenLogReviews = {
    open(kind, item) {
      state.kind = kind;
      state.item = item;
      state.key = makeKey(kind, item?.id);
      load();
    },
    close() {
      state.sequence++;
      state.item = null; state.kind = null; state.key = null;
      state.editing = false; state.review = null;
    }
  };

  async function init() {
    if (!enabled) return;
    try {
      const base = 'https://www.gstatic.com/firebasejs/12.19.0/';
      const [app, authentication, firestore] = await Promise.all([
        import(base + 'firebase-app.js'),
        import(base + 'firebase-auth.js'),
        import(base + 'firebase-firestore.js')
      ]);
      const firebaseApp = app.initializeApp({
        apiKey: config.apiKey,
        authDomain: config.authDomain,
        projectId: config.projectId,
        appId: config.appId
      });
      state.auth = authentication.getAuth(firebaseApp);
      state.db = firestore.getFirestore(firebaseApp);
      state.sdk = firestore;
      state.signIn = () => authentication.signInWithPopup(
        state.auth, new authentication.GoogleAuthProvider()
      );
      state.signOut = () => authentication.signOut(state.auth);
      authentication.onAuthStateChanged(state.auth, (user) => {
        state.user = user;
        renderSignin();
        if (state.key && !state.loading) render();
      });
      state.ready = true;
      renderSignin();
      if (state.key) load();
    } catch (error) {
      const root = reviewRoot();
      if (root) root.replaceChildren(node('p', 'review-muted',
        'Reviews are temporarily unavailable.'));
    }
  }

  if (signinButton) {
    signinButton.addEventListener('click', async () => {
      if (!state.ready) return;
      signinButton.disabled = true;
      try {
        if (state.user) await state.signOut();
        else await state.signIn();
      } catch (error) {
        if (error?.code !== 'auth/popup-closed-by-user' &&
            error?.code !== 'auth/cancelled-popup-request') {
          window.alert('Sign-in was not completed. Check Firebase authorized domains and your browser settings.');
        }
      } finally {
        signinButton.disabled = false;
      }
    });
  }
  init();
})();
