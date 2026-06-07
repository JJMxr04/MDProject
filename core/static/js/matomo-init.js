/* Matomo bootstrap — externalized version of the stock inline snippet.
 *
 * Lives in a file (not an inline <script>) because the CSP is strict:
 * `script-src 'self' ...` with no 'unsafe-inline', so inline scripts are
 * blocked site-wide. The tracker origin (pmat.warforaterra.com) is
 * allow-listed in CONTENT_SECURITY_POLICY (script-src for matomo.js,
 * connect-src for the matomo.php tracking calls, img-src for the pixel
 * fallback). Loaded from <head> of public/base.html and portal/base_app.html.
 */
var _paq = window._paq = window._paq || [];
/* tracker methods like "setCustomDimension" should be called before "trackPageView" */
/* Cookieless mode — no _pk_* cookies, so the privacy policy's "functional
 * cookies only" claim stays true and no consent banner is required (pair
 * with server-side IP anonymization: Matomo admin → Privacy → Anonymize
 * data, mask >= 2 bytes). setDoNotTrack makes honoring the browser DNT
 * signal explicit rather than relying on the server default. */
_paq.push(['disableCookies']);
_paq.push(['setDoNotTrack', true]);
_paq.push(['trackPageView']);
_paq.push(['enableLinkTracking']);
(function() {
  var u = "//pmat.warforaterra.com/";
  _paq.push(['setTrackerUrl', u + 'matomo.php']);
  _paq.push(['setSiteId', '1']);
  var d = document, g = d.createElement('script'), s = d.getElementsByTagName('script')[0];
  g.async = true; g.src = u + 'matomo.js'; s.parentNode.insertBefore(g, s);
})();
