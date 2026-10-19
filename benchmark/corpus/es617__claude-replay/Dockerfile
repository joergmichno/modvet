FROM node:22-alpine

RUN npm install -g claude-replay

EXPOSE 7331

ENTRYPOINT ["claude-replay", "--host", "0.0.0.0"]
