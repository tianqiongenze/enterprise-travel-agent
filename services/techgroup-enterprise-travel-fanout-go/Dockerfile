FROM golang:1.26.1-alpine AS builder
ENV GOPROXY=https://goproxy.cn,direct
WORKDIR /src
COPY go.mod .
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags="-s -w" -o /out/go-fanout .

FROM gcr.io/distroless/base-debian12:nonroot
WORKDIR /app
COPY --from=builder /out/go-fanout /app/go-fanout
USER nonroot:nonroot
EXPOSE 8092
ENTRYPOINT ["/app/go-fanout"]
