/* ==========================================================================
   Shared site chrome. Renders the header and footer into every page so the
   navigation lives in exactly one place. To add a page to the menu, add one
   entry to SITE.nav. Do not hand-write header or footer markup in pages.
   ========================================================================== */

const SITE = {
  name: "English Website",
  nav: [
    { label: "Home", href: "index.html" },
    { label: "About", href: "about.html" },
    { label: "Study", href: "study.html" },
  ],
  footerLinks: [
    { label: "Style guide", href: "styleguide.html" },
  ],
};

// ?theme=dark or ?theme=light forces a theme, for checking both while building.
const forcedTheme = new URLSearchParams(location.search).get("theme");
if (forcedTheme === "dark" || forcedTheme === "light") {
  document.documentElement.dataset.theme = forcedTheme;
}

function currentFile() {
  const last = location.pathname.split("/").pop();
  return last === "" ? "index.html" : last;
}

function linkList(links, linkClass) {
  return links
    .map(({ label, href }) => {
      const current = href === currentFile() ? ' aria-current="page"' : "";
      const cls = linkClass ? ` class="${linkClass}"` : "";
      return `<li><a${cls} href="${href}"${current}>${label}</a></li>`;
    })
    .join("");
}

function renderHeader(header) {
  header.innerHTML = `
    <div class="container site-header__inner">
      <a class="site-header__brand" href="index.html">${SITE.name}</a>
      <button class="site-header__toggle" type="button" aria-expanded="false" aria-controls="site-nav">Menu</button>
      <nav class="site-nav" id="site-nav" aria-label="Main">
        <ul class="site-nav__list">${linkList(SITE.nav, "site-nav__link")}</ul>
      </nav>
    </div>`;

  const toggle = header.querySelector(".site-header__toggle");
  const nav = header.querySelector(".site-nav");
  toggle.addEventListener("click", () => {
    const open = toggle.getAttribute("aria-expanded") !== "true";
    toggle.setAttribute("aria-expanded", String(open));
    toggle.textContent = open ? "Close" : "Menu";
    nav.toggleAttribute("data-open", open);
  });
}

function renderFooter(footer) {
  footer.innerHTML = `
    <div class="container site-footer__inner">
      <span class="site-footer__name">${SITE.name}</span>
      <ul class="site-footer__list">${linkList(SITE.footerLinks)}</ul>
      <span>&copy; ${new Date().getFullYear()}</span>
    </div>`;
}

document.querySelectorAll("[data-site-header]").forEach(renderHeader);
document.querySelectorAll("[data-site-footer]").forEach(renderFooter);
