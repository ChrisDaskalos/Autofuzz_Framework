/*
 * ringbuf.h - a small ring buffer (FIFO) of bytes.
 *
 * The caller gives the memory: ringbuf_init(&rb, storage, sizeof storage).
 * Part of the AutoFuzz example project (see ../README.md).
 */
#ifndef RINGBUF_H
#define RINGBUF_H

#include <stddef.h>
#include <stdint.h>

typedef struct {
    uint8_t *data;   /* storage given by the caller */
    size_t cap;      /* number of bytes in data */
    size_t head;     /* next write position */
    size_t tail;     /* next read position */
    size_t count;    /* bytes stored now */
} ringbuf_t;

/* Use `storage` (cap bytes) as an empty ring buffer. */
void ringbuf_init(ringbuf_t *rb, uint8_t *storage, size_t cap);

/* Remove everything. */
void ringbuf_clear(ringbuf_t *rb);

/* Add one byte at the end. Returns 0, or -1 if the buffer is full. */
int ringbuf_push(ringbuf_t *rb, uint8_t value);

/* Remove the oldest byte. Returns it (0..255), or -1 if empty. */
int ringbuf_pop(ringbuf_t *rb);

/* Read the byte at position idx (0 = oldest) without removing it.
 * Returns it (0..255), or -1 if idx is not stored. */
int ringbuf_peek(const ringbuf_t *rb, size_t idx);

size_t ringbuf_count(const ringbuf_t *rb);
int ringbuf_is_full(const ringbuf_t *rb);

#endif /* RINGBUF_H */
