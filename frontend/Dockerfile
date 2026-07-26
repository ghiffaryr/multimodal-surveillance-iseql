FROM node:20-alpine

WORKDIR /app

# Install pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate

# Install deps first for better layer caching.
COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile

# Copy source.
COPY . .

# Build.
RUN pnpm build

# SvelteKit's `vite preview` serves the built app.
ENV HOST=0.0.0.0
ENV PORT=5173

EXPOSE 5173

CMD ["pnpm", "preview", "--host", "0.0.0.0", "--port", "5173"]
