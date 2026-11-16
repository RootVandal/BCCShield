// Tailwind 3.4.16, the same version the pages used from the CDN. After changing classes in static/*.html or
// static/js/*.js rebuild the stylesheet (needs Node.js):
//   npx tailwindcss@3.4.16 -i static/css/tailwind.src.css -o static/css/tailwind.css --minify
module.exports = {
  content: ["./static/*.html", "./static/js/*.js"],
  theme: { extend: {} },
  plugins: [],
};
