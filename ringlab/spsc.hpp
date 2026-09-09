#pragma once
#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>

// Exactly one producer and one consumer. Object lifetime is externally synchronized.
template<std::size_t Capacity> class SpscRing {
 static_assert(Capacity > 0);
 static_assert(std::atomic<std::size_t>::is_always_lock_free);
 struct alignas(64) Index { std::atomic<std::size_t> value{0}; };
 std::array<std::uint64_t, Capacity + 1> data_{};
 Index head_, tail_;
public:
 bool push(std::uint64_t value) noexcept {
  const auto head = head_.value.load(std::memory_order_relaxed);
  const auto next = (head + 1) % (Capacity + 1);
  if(next == tail_.value.load(std::memory_order_acquire)) return false;
  data_[head] = value;
  head_.value.store(next, std::memory_order_release);
  return true;
 }
 bool pop(std::uint64_t& value) noexcept {
  const auto tail = tail_.value.load(std::memory_order_relaxed);
  if(tail == head_.value.load(std::memory_order_acquire)) return false;
  value = data_[tail];
  tail_.value.store((tail + 1) % (Capacity + 1), std::memory_order_release);
  return true;
 }
};
