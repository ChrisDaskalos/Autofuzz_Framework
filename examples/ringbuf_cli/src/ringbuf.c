/*
 * ringbuf.c - a small ring buffer (FIFO) of bytes.
 *
 * Contains ONE bug on purpose (see ../README.md): the wrap check in
 * ringbuf_push uses ">" where it must use ">=".
 */
#include "ringbuf.h"

void ringbuf_init(ringbuf_t *rb, uint8_t *storage, size_t cap)
{
    if (rb == NULL) {
        return;
    }
    rb->data = storage;
    rb->cap = (storage != NULL) ? cap : 0;
    ringbuf_clear(rb);
}

void ringbuf_clear(ringbuf_t *rb)
{
    if (rb == NULL) {
        return;
    }
    rb->head = 0;
    rb->tail = 0;
    rb->count = 0;
}

int ringbuf_push(ringbuf_t *rb, uint8_t value)
{
    if (rb == NULL || rb->count >= rb->cap) {
        return -1;
    }
    rb->data[rb->head] = value;
    rb->head++;
    if (rb->head > rb->cap) {   /* BUG (on purpose): must be >= */
        rb->head = 0;
    }
    rb->count++;
    return 0;
}

int ringbuf_pop(ringbuf_t *rb)
{
    if (rb == NULL || rb->count == 0) {
        return -1;
    }
    uint8_t value = rb->data[rb->tail];
    rb->tail++;
    if (rb->tail >= rb->cap) {
        rb->tail = 0;
    }
    rb->count--;
    return value;
}

int ringbuf_peek(const ringbuf_t *rb, size_t idx)
{
    if (rb == NULL || idx >= rb->count) {
        return -1;
    }
    return rb->data[(rb->tail + idx) % rb->cap];
}

size_t ringbuf_count(const ringbuf_t *rb)
{
    return (rb != NULL) ? rb->count : 0;
}

int ringbuf_is_full(const ringbuf_t *rb)
{
    return rb != NULL && rb->count >= rb->cap;
}
