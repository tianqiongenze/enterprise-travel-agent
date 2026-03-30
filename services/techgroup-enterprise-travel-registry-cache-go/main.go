// Package main provides the service entrypoint.
package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/golang/groupcache"
	json "github.com/goccy/go-json"
	"github.com/gin-gonic/gin"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
)

type CacheResponse struct {
	Key    string `json:"key"`
	Value  string `json:"value"`
	Source string `json:"source"`
}

var cacheGroup *groupcache.Group
var cachePool *groupcache.HTTPPool
var peerCount int64
var peerRefreshUnix int64
var peerRefreshErrors int64
var cacheMu sync.RWMutex
var cacheStore = map[string]cacheEntry{}

type cacheEntry struct {
	value     string
	expiresAt time.Time
}

func main() {
	gin.SetMode(gin.ReleaseMode)
	r := gin.New()
	r.Use(gin.Recovery())

	self := os.Getenv("GROUPCACHE_SELF")
	if self == "" {
		self = "http://go-registry-cache-0.go-registry-cache-headless.default.svc.cluster.local:8093"
	}
	cachePool = groupcache.NewHTTPPool(self)

	cacheGroup = groupcache.NewGroup("registry-cache", 64<<20, groupcache.GetterFunc(
		func(ctx context.Context, key string, dest groupcache.Sink) error {
			cacheMu.RLock()
			entry, ok := cacheStore[key]
			cacheMu.RUnlock()
			if !ok {
				return fmt.Errorf("miss")
			}
			if time.Now().After(entry.expiresAt) {
				cacheMu.Lock()
				delete(cacheStore, key)
				cacheMu.Unlock()
				return fmt.Errorf("miss")
			}
			return dest.SetString(entry.value)
		},
	))

	peers := os.Getenv("GROUPCACHE_PEERS")
	if peers != "" {
		cachePool.Set(strings.Split(peers, ",")...)
	}

	go startPeerWatcher()

	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok"})
	})

	r.GET("/metrics", func(c *gin.Context) {
		body := ""
		body += fmt.Sprintf("groupcache_peers_count %d\n", atomic.LoadInt64(&peerCount))
		body += fmt.Sprintf("groupcache_peer_refresh_timestamp %d\n", atomic.LoadInt64(&peerRefreshUnix))
		body += fmt.Sprintf("groupcache_peer_refresh_errors_total %d\n", atomic.LoadInt64(&peerRefreshErrors))
		c.Data(http.StatusOK, "text/plain; version=0.0.4", []byte(body))
	})

	r.GET("/v1/cache/get/:key", func(c *gin.Context) {
		key := c.Param("key")
		var out string
		ctx, cancel := context.WithTimeout(context.Background(), time.Second)
		defer cancel()
		if err := cacheGroup.Get(ctx, key, groupcache.StringSink(&out)); err != nil {
			c.JSON(http.StatusNotFound, gin.H{"error": "miss"})
			return
		}
		c.JSON(http.StatusOK, CacheResponse{Key: key, Value: out, Source: "groupcache"})
	})

	r.POST("/v1/cache/set", func(c *gin.Context) {
		var payload struct {
			Key   string `json:"key"`
			Value string `json:"value"`
		}
		decoder := json.NewDecoder(c.Request.Body)
		decoder.DisallowUnknownFields()
		if err := decoder.Decode(&payload); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}
		cacheMu.Lock()
		cacheStore[payload.Key] = cacheEntry{value: payload.Value, expiresAt: time.Now().Add(30 * time.Second)}
		cacheMu.Unlock()
		c.JSON(http.StatusOK, gin.H{"status": "ok"})
	})

	port := os.Getenv("GO_REGISTRY_CACHE_PORT")
	if port == "" {
		port = "8093"
	}
	_ = r.Run(":" + port)
}

func startPeerWatcher() {
	namespace := os.Getenv("POD_NAMESPACE")
	if namespace == "" {
		namespace = "default"
	}
	serviceName := os.Getenv("GROUPCACHE_HEADLESS_SERVICE")
	if serviceName == "" {
		serviceName = "go-registry-cache-headless"
	}

	config, err := rest.InClusterConfig()
	if err != nil {
		return
	}
	clientset, err := kubernetes.NewForConfig(config)
	if err != nil {
		return
	}

	go func() {
		for {
			watcher, watchErr := clientset.CoreV1().Endpoints(namespace).Watch(
				context.Background(),
				metav1.SingleObject(metav1.ObjectMeta{Name: serviceName}),
			)
			if watchErr != nil {
				time.Sleep(2 * time.Second)
				continue
			}
			refreshPeersFromEndpoints(clientset, namespace, serviceName)
			for range watcher.ResultChan() {
				refreshPeersFromEndpoints(clientset, namespace, serviceName)
			}
			watcher.Stop()
			time.Sleep(500 * time.Millisecond)
		}
	}()

	ticker := time.NewTicker(15 * time.Second)
	defer ticker.Stop()
	for range ticker.C {
		refreshPeersFromEndpoints(clientset, namespace, serviceName)
	}
}

func refreshPeersFromEndpoints(clientset *kubernetes.Clientset, namespace string, serviceName string) {
	eps, getErr := clientset.CoreV1().Endpoints(namespace).Get(context.Background(), serviceName, metav1.GetOptions{})
	if getErr != nil {
		atomic.AddInt64(&peerRefreshErrors, 1)
		return
	}
	var peers []string
	for _, subset := range eps.Subsets {
		for _, addr := range subset.Addresses {
			if addr.IP != "" {
				peers = append(peers, "http://"+addr.IP+":8093")
			}
		}
	}
	if len(peers) > 0 {
		cachePool.Set(peers...)
		atomic.StoreInt64(&peerCount, int64(len(peers)))
		atomic.StoreInt64(&peerRefreshUnix, time.Now().Unix())
	}
}
