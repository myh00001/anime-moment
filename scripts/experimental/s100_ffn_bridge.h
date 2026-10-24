#pragma once
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <fcntl.h>
#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

static bool s100_ffn_layer_enabled(int layer) {
    const char * value = std::getenv("S100_FFN_LAYERS");
    if (!value) return layer == 0;
    std::string list = std::string(",") + value + ",";
    return list.find("," + std::to_string(layer) + ",") != std::string::npos;
}
static void s100_ffn_io(int fd, void * data, size_t length, bool sending) {
    char * p = (char *)data;
    while (length) {
        ssize_t n = sending ? send(fd,p,length,MSG_NOSIGNAL) : recv(fd,p,length,0);
        if (n < 0 && errno == EINTR) continue;
        GGML_ASSERT(n > 0);
        p += n; length -= (size_t)n;
    }
}
static void s100_ffn_dump(ggml_tensor * dst,const ggml_tensor * src,int ith,int nth,void * user) {
    if (ith != 0) return;
    (void)nth;
    GGML_ASSERT(src->type == GGML_TYPE_F32 && ggml_is_contiguous(src));
    std::memcpy(dst->data,src->data,ggml_nbytes(src));
    const char * directory = std::getenv("S100_FFN_DUMP_DIR");
    if (!directory) return;
    int layer = (int)(intptr_t)user;
    std::string path = std::string(directory)+"/ffn-"+std::to_string(layer)+"-t"+std::to_string(src->ne[1])+".bin";
    int fd = open(path.c_str(),O_WRONLY|O_CREAT|O_TRUNC,0600); GGML_ASSERT(fd >= 0);
    uint32_t header[2] = {(uint32_t)src->ne[1],(uint32_t)src->ne[0]};
    GGML_ASSERT(write(fd,header,sizeof(header)) == sizeof(header));
    const char * p = (const char *)src->data;size_t length=ggml_nbytes(src);
    while(length) {ssize_t n=write(fd,p,length); if(n<0 && errno==EINTR)continue;GGML_ASSERT(n>0);p+=n;length-=n;}
    close(fd);
}
static void s100_ffn_offload(ggml_tensor * dst,const ggml_tensor * src,int ith,int nth,void * user) {
    if (ith != 0) return;
    (void)nth;
    GGML_ASSERT(src->type == GGML_TYPE_F32 && ggml_is_contiguous(src));
    const char * path = std::getenv("S100_FFN_SOCKET");GGML_ASSERT(path);
    int layer=(int)(intptr_t)user;
    int fd=socket(AF_UNIX,SOCK_STREAM,0);GGML_ASSERT(fd>=0);
    timeval timeout{15,0};setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&timeout,sizeof(timeout));
    sockaddr_un address{};address.sun_family=AF_UNIX;
    GGML_ASSERT(std::strlen(path)<sizeof(address.sun_path));std::strcpy(address.sun_path,path);
    GGML_ASSERT(connect(fd,(sockaddr*)&address,sizeof(address))==0);
    uint32_t header[4]={0x5346464e,(uint32_t)layer,(uint32_t)src->ne[0],(uint32_t)src->ne[1]};
    s100_ffn_io(fd,header,sizeof(header),true);
    s100_ffn_io(fd,src->data,ggml_nbytes(src),true);
    uint32_t reply[5]{};s100_ffn_io(fd,reply,sizeof(reply),false);
    GGML_ASSERT(reply[0]==header[0] && reply[1]==header[1] && reply[2]==header[2] && reply[3]==header[3] && reply[4]==0);
    s100_ffn_io(fd,dst->data,ggml_nbytes(dst),false);close(fd);
    std::fprintf(stderr,"S100_FFN_USED layer=%d tokens=%lld\n",layer,(long long)src->ne[1]);
}
static ggml_tensor * s100_ffn_prepare(ggml_context * ctx,ggml_tensor * cur,int layer) {
    if (cur->ne[1]>1 && s100_ffn_layer_enabled(layer) && std::getenv("S100_FFN_DUMP_DIR"))
        return ggml_map_custom1(ctx,cur,s100_ffn_dump,1,(void *)(intptr_t)layer);
    return cur;
}
static ggml_tensor * s100_ffn_try(ggml_context * ctx,ggml_tensor * cur,int layer) {
    if (!std::getenv("S100_FFN_SOCKET") || !s100_ffn_layer_enabled(layer) || cur->ne[0]!=1536 || cur->ne[1]<128 || cur->ne[1]>256 || cur->ne[2]!=1 || cur->ne[3]!=1) return nullptr;
    return ggml_map_custom1(ctx,cur,s100_ffn_offload,1,(void *)(intptr_t)layer);
}
