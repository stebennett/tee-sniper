# Build stage
FROM golang:1.25-alpine AS builder

WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o tee-sniper cmd/tee-sniper/main.go

# Runtime stage
FROM alpine:3.21

RUN apk --no-cache add ca-certificates tzdata
WORKDIR /app
COPY --from=builder /app/tee-sniper .

ENTRYPOINT ["/app/tee-sniper"]
