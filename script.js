const body = document.body;
const toggle = document.querySelector(".menu-toggle");
const navLinks = document.querySelector(".nav-links");

if (toggle && navLinks) {
  toggle.addEventListener("click", () => {
    const isOpen = body.classList.toggle("nav-open");
    toggle.setAttribute("aria-expanded", String(isOpen));
  });

  navLinks.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      body.classList.remove("nav-open");
      toggle.setAttribute("aria-expanded", "false");
    });
  });
}

const currentPage = window.location.pathname.split("/").pop() || "index.html";
document.querySelectorAll(".nav-links a").forEach((link) => {
  const href = link.getAttribute("href");
  if (href === currentPage) {
    link.classList.add("active");
  }
});

const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("visible");
        observer.unobserve(entry.target);
      }
    });
  },
  { threshold: 0.18 }
);

document.querySelectorAll(".reveal").forEach((item, index) => {
  item.style.transitionDelay = `${Math.min(index * 45, 360)}ms`;
  observer.observe(item);
});

const consultForm = document.querySelector(".consult-form");
if (consultForm) {
  consultForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const button = consultForm.querySelector('button[type="submit"]');
    if (button) {
      button.textContent = "已提交，顾问将尽快联系你";
      button.setAttribute("disabled", "true");
    }
  });
}
