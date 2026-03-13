# Security & DDoS Protection

## Architecture overview

- **Static site**: GitHub Pages (gilly.co.il)
- **Backend**: Firebase/Firestore (project: gillygeoguesser)
- **Bot protection**: Firebase App Check with reCAPTCHA v3

## Protection layers

### 1. Cloudflare (recommended — free tier)

GitHub Pages has no built-in DDoS protection. Adding Cloudflare as a DNS proxy
is the standard free solution for static sites.

**Setup steps:**

1. Create a free Cloudflare account at https://cloudflare.com
2. Add the `gilly.co.il` domain
3. Cloudflare will scan existing DNS records — verify they're correct
4. Change the domain's nameservers at your registrar to the ones Cloudflare provides
5. In the Cloudflare dashboard, ensure the DNS record for `gilly.co.il` has the
   **orange cloud** (proxy) enabled — this routes traffic through Cloudflare
6. Under **Security → Settings**, set Security Level to "Medium" or "High"
7. Under **Security → Bots**, enable Bot Fight Mode (free)
8. Under **Speed → Optimization**, enable Auto Minify for JS/CSS/HTML
9. Under **Caching → Configuration**, set Browser Cache TTL to "Respect Existing Headers"

**What Cloudflare provides:**

- DDoS mitigation (automatic, free tier handles most attacks)
- Web Application Firewall (WAF) with managed rulesets
- Rate limiting (5 free rules)
- Bot detection and management
- SSL/TLS termination
- CDN caching (reduces load on GitHub Pages)
- Under-attack mode (one-click for active attacks)

### 2. Firebase App Check (already enabled)

App Check uses reCAPTCHA v3 to verify requests come from your real app.

**Critical**: Enable **enforcement** in the Firebase Console:

1. Go to Firebase Console → App Check → Firestore
2. Click **Enforce**
3. This blocks all requests that don't pass reCAPTCHA verification,
   including direct REST API calls from attackers

Without enforcement, App Check only logs violations but doesn't block them.

### 3. Firestore Security Rules (firestore.rules)

The `firestore.rules` file contains hardened rules with:

- Authentication checks (no anonymous writes)
- Field validation (types, ranges, allowed fields)
- Write-once daily scores (no updates)
- Document ownership verification

**Deploy rules:**

```bash
# Install Firebase CLI if needed
npm install -g firebase-tools

# Login and deploy rules
firebase login
firebase init firestore  # select existing project: gillygeoguesser
firebase deploy --only firestore:rules
```

Or copy-paste the rules directly in the Firebase Console → Firestore → Rules.

### 4. Firebase Console hardening

- [ ] **Budget alerts**: GCP Console → Billing → Budgets & alerts → Create at $5, $10, $25
- [ ] **Daily quotas**: GCP Console → APIs → Firestore → Quotas → Set daily read/write limits
- [ ] **Email enumeration protection**: Firebase Console → Authentication → Settings → Enable
- [ ] **Auth rate limits**: Verify default rate limits are active (100 signups/IP/hour)
- [ ] **App Check enforcement**: Firebase Console → App Check → Firestore → Enforce

### 5. Client-side rate limiting (index.html)

Firebase operations in the app are wrapped with cooldown timers to prevent
rapid-fire requests from the browser (e.g., button mashing, scripted abuse):

| Operation | Cooldown |
|-----------|----------|
| Save game score | 10 seconds |
| Save daily score | 30 seconds |
| Load leaderboard | 5 seconds |
| Load history | 5 seconds |
