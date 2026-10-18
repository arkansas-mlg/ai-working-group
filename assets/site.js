/* Progressive enhancement: all content and links work without JavaScript. */
(() => {
  "use strict";
  document.documentElement.classList.add("js");
  const toggle = document.querySelector(".menu-toggle");
  const navigation = document.querySelector(".site-nav");
  if (toggle && navigation) {
    const closeMenu = () => {
      toggle.setAttribute("aria-expanded", "false");
      navigation.classList.remove("is-open");
    };
    toggle.addEventListener("click", () => {
      const open = toggle.getAttribute("aria-expanded") !== "true";
      toggle.setAttribute("aria-expanded", String(open));
      navigation.classList.toggle("is-open", open);
    });
    navigation.addEventListener("click", event => {
      if (event.target.closest("a")) closeMenu();
    });
    document.addEventListener("keydown", event => {
      if (event.key === "Escape" && toggle.getAttribute("aria-expanded") === "true") {
        closeMenu();
        toggle.focus();
      }
    });
    document.addEventListener("click", event => {
      if (!event.target.closest(".header-inner")) closeMenu();
    });
  }

  // The same day boundary is used by the generator and by browser previews.
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Chicago", year: "numeric", month: "2-digit", day: "2-digit"
  }).formatToParts(new Date());
  const part = name => parts.find(p => p.type === name).value;
  const today = `${part("year")}-${part("month")}-${part("day")}`;
  document.querySelectorAll("[data-preview-entry]").forEach(entry => {
    const boundary = entry.dataset.date || entry.dataset.deadline;
    if (boundary && boundary < today) entry.hidden = true;
  });
  document.querySelectorAll("[data-preview-empty]").forEach(empty => {
    empty.hidden = Array.from(empty.parentElement.querySelectorAll("[data-preview-entry]"))
      .some(entry => !entry.hidden);
  });

  document.querySelectorAll("[data-collection]").forEach(collection => {
    const form = collection.querySelector("[data-filters]");
    if (!form) return;
    const entries = Array.from(collection.querySelectorAll("[data-entry]"));
    const search = form.querySelector("[name=q]");
    const type = form.querySelector("[name=type]");
    const status = form.querySelector("[name=status]");
    const selectFields = [type, status].filter(Boolean);
    const fields = [search, ...selectFields];
    const count = collection.querySelector("[data-result-count]");
    const empty = collection.querySelector("[data-no-results]");
    const isEvents = collection.dataset.collection === "events";

    // Keep deadlines current between static builds, using the group's time zone.
    entries.forEach(entry => {
      const boundary = isEvents ? entry.dataset.date : entry.dataset.deadline;
      if (boundary && boundary < today) {
        const label = isEvents ? "Past" : "Closed";
        entry.dataset.status = label;
        let badge = entry.querySelector("[data-status-label]");
        if (!badge) {
          badge = document.createElement("span");
          badge.className = "badge badge-status";
          badge.dataset.statusLabel = "";
          entry.querySelector(".item-meta").append(badge);
        }
        badge.textContent = label;
        badge.classList.add("badge-closed");
      }
    });
    // Rebuild the status options after refreshing expired entries.
    if (status) {
      status.replaceChildren(new Option("All statuses", ""));
      [...new Set(entries.map(entry => entry.dataset.status).filter(Boolean))]
        .sort().forEach(value => status.add(new Option(value, value)));
    }

    const params = new URLSearchParams(window.location.search);
    search.value = params.get("q") || "";
    for (const field of selectFields) {
      const value = params.get(field.name);
      if (value && Array.from(field.options).some(option => option.value === value)) field.value = value;
    }
    const applyFilters = (updateURL = true) => {
      const words = search.value.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
      let visible = 0;
      entries.forEach(entry => {
        const matches = words.every(word => entry.dataset.search.includes(word))
          && (!type.value || entry.dataset.type === type.value)
          && (!status || !status.value || entry.dataset.status === status.value);
        entry.hidden = !matches;
        if (matches) visible += 1;
      });
      count.textContent = `${visible} of ${entries.length} ${isEvents ? "activities" : "listings"}`;
      empty.hidden = visible !== 0;
      if (updateURL) {
        const next = new URL(window.location.href);
        for (const field of fields) {
          if (field.value) next.searchParams.set(field.name, field.value);
          else next.searchParams.delete(field.name);
        }
        if (!status) next.searchParams.delete("status");
        window.history.replaceState(null, "", next);
      }
    };
    form.addEventListener("submit", event => event.preventDefault());
    search.addEventListener("input", () => applyFilters());
    selectFields.forEach(field => field.addEventListener("change", () => applyFilters()));
    form.addEventListener("reset", () => {
      fields.forEach(field => { field.value = ""; });
      applyFilters();
    });
    collection.querySelector("[data-clear-filters]").addEventListener("click", () => {
      form.reset();
      search.focus();
    });
    form.hidden = false;
    applyFilters(!status && params.has("status"));
  });
})();
