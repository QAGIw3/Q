# --- Build Stage ---
FROM node:18-alpine AS build

# Set working directory
WORKDIR /app

# Copy package.json and package-lock.json
COPY ./WebAppQ/app/package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the application's source code
COPY ./WebAppQ/app ./

# Build the React application
RUN npm run build

# --- Serve Stage ---
FROM nginx:1.21-alpine

# Copy the built static files from the build stage to the Nginx server directory
COPY --from=build /app/build /usr/share/nginx/html

# Copy a custom Nginx configuration file
# This is important for single-page applications (SPAs)
COPY ./WebAppQ/nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"] 