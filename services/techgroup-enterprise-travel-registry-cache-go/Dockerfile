FROM golang:1.26.1-alpine AS builder
WORKDIR /src
COPY go.mod .
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags="-s -w" -o /out/go-registry-cache ./main.go

FROM gcr.io/distroless/base-debian12:nonroot
WORKDIR /app
COPY --from=builder /out/go-registry-cache /app/go-registry-cache
USER nonroot:nonroot
EXPOSE 8093
ENTRYPOINT ["/app/go-registry-cache"]
