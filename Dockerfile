# Build stage
FROM dhi.io/golang:1.25-alpine3.23-dev AS builder

WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o tee-sniper cmd/tee-sniper/main.go

# Runtime stage

FROM dhi.io/alpine-base:3.23

WORKDIR /app

COPY --from=builder --chown=nonroot:nonroot /app/tee-sniper .

USER nonroot

ENTRYPOINT ["/app/tee-sniper"]
