# Docker learning notes

I noticed that rebuilding my FastAPI image after changing only application code is much faster when dependency installation stays in an earlier layer.

Pinning the Python base image tag made local builds feel more repeatable while I prepare for packaging a model-serving API.

I still get confused about when `EXPOSE` actually makes a port reachable from my laptop versus when I need `-p`.

Next I want to understand how the same container image becomes a Kubernetes Deployment for inference workloads.
