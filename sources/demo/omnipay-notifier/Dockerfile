FROM golang:1.23-alpine AS build

WORKDIR /src
COPY . .
RUN go build -o /out/notifier ./cmd/notifier

FROM alpine:3.21
COPY --from=build /out/notifier /usr/local/bin/notifier

ENTRYPOINT ["/usr/local/bin/notifier"]
