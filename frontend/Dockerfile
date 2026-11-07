FROM node:22-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

# Normalise webroot permissions. Without this, every file under public/ is served as 403.
#
# Why: this repo lives on an SMB share that presents every file as 0700. `COPY . .` carries
# those modes into the builder, and Vite copies public/* into dist VERBATIM, preserving mode,
# while generating assets/*.js|css fresh at 0644. nginx workers run as uid 101 (nginx), so the
# 0700 root-owned files are unreadable to them: index.html and assets/* load fine (0644) while
# the logo, favicons, manifest.json and sw.js all 403. That breaks the PWA manifest and makes
# ServiceWorker registration fail. Diagnosed 2026-11-07.
#
# Do NOT replace this with `COPY --chmod=644`: that sets directories to 644 too, which strips
# the +x they need to be traversable, and assets/ stops working.
RUN find /usr/share/nginx/html -type d -exec chmod 755 {} + \
 && find /usr/share/nginx/html -type f -exec chmod 644 {} +

COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
