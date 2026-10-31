/* Progressive enhancement: all author profiles remain in the HTML and are
   readable without JavaScript. No profile data is loaded from a service. */
(() => {
  const tools = document.querySelector("[data-team-tools]");
  const search = document.querySelector("[data-team-search]");
  const role = document.querySelector("[data-team-role]");
  const reset = document.querySelector("[data-team-reset]");
  const status = document.querySelector("[data-team-status]");
  const empty = document.querySelector("[data-team-empty]");
  const profiles = [...document.querySelectorAll("[data-team-profile]")];

  if (!tools || !search || !role || !reset || !status || !empty || !profiles.length) return;

  function filterProfiles() {
    const query = search.value.trim().toLocaleLowerCase("en");
    let visible = 0;

    profiles.forEach((profile) => {
      const nameMatches = profile.dataset.name.toLocaleLowerCase("en").includes(query);
      const roleMatches = !role.value || profile.dataset.role === role.value;
      profile.hidden = !(nameMatches && roleMatches);
      if (!profile.hidden) visible += 1;
    });

    status.textContent = `Showing ${visible} of ${profiles.length} authors.`;
    empty.hidden = visible !== 0;
  }

  search.addEventListener("input", filterProfiles);
  role.addEventListener("change", filterProfiles);
  reset.addEventListener("click", () => {
    search.value = "";
    role.value = "";
    filterProfiles();
    search.focus();
  });

  tools.hidden = false;
  filterProfiles();
})();
