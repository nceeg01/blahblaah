#include "spsc.hpp"
#include <algorithm>
#include <chrono>
#include <iostream>
#include <mutex>
#include <thread>
#include <stdexcept>
#include <vector>

template<std::size_t C> class MutexRing {
 std::array<std::uint64_t,C> data_{}; std::size_t head_=0,tail_=0,count_=0; std::mutex mutex_;
public:
 bool push(std::uint64_t v){std::lock_guard lock(mutex_);if(count_==C)return false;data_[head_]=v;head_=(head_+1)%C;++count_;return true;}
 bool pop(std::uint64_t& v){std::lock_guard lock(mutex_);if(!count_)return false;v=data_[tail_];tail_=(tail_+1)%C;--count_;return true;}
};
void require(bool condition){if(!condition)throw std::runtime_error("FIFO correctness failure");}
template<class Q> double transfer(std::size_t n){
 Q q;std::atomic<bool> start=false;bool ordered=true;
 std::thread producer([&]{while(!start.load(std::memory_order_acquire))std::this_thread::yield();for(std::size_t i=0;i<n;i++)while(!q.push(i))std::this_thread::yield();});
 std::thread consumer([&]{while(!start.load(std::memory_order_acquire))std::this_thread::yield();for(std::size_t i=0;i<n;i++){std::uint64_t v;while(!q.pop(v))std::this_thread::yield();if(v!=i)ordered=false;}});
 const auto begin=std::chrono::steady_clock::now();start.store(true,std::memory_order_release);producer.join();consumer.join();
 const double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count();require(ordered);return n/seconds;
}
void tests(){SpscRing<3> q;std::uint64_t value=99;require(!q.pop(value)&&value==99);for(unsigned i=0;i<3;i++)require(q.push(i));require(!q.push(9));for(unsigned i=0;i<3;i++){require(q.pop(value));require(value==i);}for(unsigned i=0;i<10000;i++){require(q.push(i));require(q.pop(value)&&value==i);}transfer<SpscRing<1>>(10000);transfer<SpscRing<1024>>(1000000);std::cout<<"PASS: empty, full, FIFO, wraparound, capacity-one and 1,000,000 concurrent transfers\n";}
int main(int argc,char** argv){try{if(argc>1&&std::string(argv[1])=="--test"){tests();return 0;}std::vector<double> a,b;for(int round=0;round<5;round++){if(round%2){b.push_back(transfer<MutexRing<1024>>(1000000));a.push_back(transfer<SpscRing<1024>>(1000000));}else{a.push_back(transfer<SpscRing<1024>>(1000000));b.push_back(transfer<MutexRing<1024>>(1000000));}}std::sort(a.begin(),a.end());std::sort(b.begin(),b.end());std::cout<<"{\"messages\":1000000,\"rounds\":5,\"capacity\":1024,\"spsc_per_second\":"<<a[2]<<",\"mutex_per_second\":"<<b[2]<<",\"ratio\":"<<a[2]/b[2]<<",\"hardware_threads\":"<<std::thread::hardware_concurrency()<<",\"compiler\":\""<<__VERSION__<<"\",\"environment\":\"Shared Linux build container; unpinned threads\"}\n";}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
