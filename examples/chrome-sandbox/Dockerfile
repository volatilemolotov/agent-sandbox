# Use a base image with a minimal set of packages.
FROM debian:13-slim

#----------------------
# Install general prerequisite packages.
RUN apt-get update && apt-get install -y \
    ca-certificates \
    wget \
    xdg-utils \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

#----------------------
# Install necessary packages for Chrome (dpkg package requires them)
RUN apt-get update && apt-get install -y \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libc6 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libexpat1 \
    libcurl4 \
    libgbm1 \
    libgtk-4-1 \
    libnss3 \
    libpango-1.0-0 \
    libvulkan1 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Download and install Google Chrome from dpkg
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && dpkg -i google-chrome-stable_current_amd64.deb \
    && rm google-chrome-stable_current_amd64.deb

# Create a non-root user to run Chrome.
RUN groupadd -r chrome && useradd -r -g chrome -G audio,video chrome \
    && mkdir -p /home/chrome/Downloads && chown -R chrome:chrome /home/chrome

#----------------------
# Install VNC
RUN apt-get update  \
    && apt-get install --yes tigervnc-standalone-server --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# We need xdpyinfo to check that the X server is up
RUN apt-get update  \
    && apt-get install --yes x11-utils --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# If we want to create vnc screenshots, we need xwd
RUN apt-get update  \
    && apt-get install --yes x11-apps --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Precreate X11 stuff
RUN mkdir -p /tmp/.X11-unix
RUN chmod 1777 /tmp/.X11-unix

#----------------------
# Add our entrypoint script
COPY --chmod=a+rx chrome-sandbox-entrypoint /chrome-sandbox-entrypoint
RUN chmod a+rx /chrome-sandbox-entrypoint

#----------------------
# Configure entrypoint, user, etc

WORKDIR /home/chrome

USER chrome

# Set the entrypoint to run our script.
ENTRYPOINT [ "/chrome-sandbox-entrypoint" ]
