/* Prints each swatch's current token value, so the style guide never drifts
   from tokens.css. Re-runs when the OS theme changes. */

function fillSwatchValues() {
  const styles = getComputedStyle(document.documentElement);
  document.querySelectorAll("[data-token]").forEach((el) => {
    el.textContent = styles.getPropertyValue(el.dataset.token).trim();
  });
}

fillSwatchValues();
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", fillSwatchValues);
