FROM node:18-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm install

RUN apk add --no-cache imagemagick librsvg

COPY . .
RUN magick public/icon.svg -background none -resize 180x180 public/apple-touch-icon.png && \
    magick public/icon.svg -background none -resize 192x192 public/icon-192.png && \
    magick public/icon.svg -background none -resize 512x512 public/icon-512.png
RUN npm run build

FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
