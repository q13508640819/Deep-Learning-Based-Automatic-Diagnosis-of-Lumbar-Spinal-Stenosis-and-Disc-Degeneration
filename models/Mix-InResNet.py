import torch
import torch.nn as nn
import os
import sys

class BasicConv2d(nn.Module):

    def __init__(self, in_planes, out_planes, kernel_size, stride, padding=0):
        super(BasicConv2d, self).__init__()
        self.conv = nn.Conv2d(in_planes, out_planes,
                              kernel_size=kernel_size, stride=stride,
                              padding=padding, bias=False) # verify bias false
        self.bn = nn.BatchNorm2d(out_planes,
                                 eps=0.001, # value found in tensorflow
                                 momentum=0.1, # default pytorch value
                                 affine=True)
        self.relu = nn.ReLU(inplace=False)

    def forward(self, x):
        x = self.conv(x)
        x = self.bn(x)
        x = self.relu(x)
        return x
    
class DepthSeperabelConv2d(nn.Module):

    def __init__(self, input_channels, output_channels, kernel_size, **kwargs):
        super().__init__()
        self.depthwise = nn.Sequential(
            nn.Conv2d(
                input_channels,
                input_channels,
                kernel_size,
                groups=input_channels,
                **kwargs),
            nn.BatchNorm2d(input_channels),
            nn.ReLU(inplace=True)
        )

        self.pointwise = nn.Sequential(
            nn.Conv2d(input_channels, output_channels, 1),
            nn.BatchNorm2d(output_channels),
            nn.ReLU(inplace=True)
        )

    def forward(self, x):
        x = self.depthwise(x)
        x = self.pointwise(x)

        return x       

    
class MixedConv2d(nn.Module):
    def __init__(self, input_channels, output_channels, kernel_size, **kwargs):
        super().__init__()

        self.depthwise_separable = DepthSeperabelConv2d(
            input_channels, output_channels, kernel_size, padding=1, **kwargs)
        
        self.standard_conv = nn.Sequential(
            nn.Conv2d(input_channels, output_channels, kernel_size, padding=1, **kwargs),
            nn.BatchNorm2d(output_channels),
            nn.ReLU(inplace=True)
        )

        self.dilated_conv = nn.Sequential(
            nn.Conv2d(input_channels, output_channels, kernel_size, dilation=2, padding=2, **kwargs),
            nn.BatchNorm2d(output_channels),
            nn.ReLU(inplace=True)
        )

        self.pointwise = nn.Conv2d(3 * output_channels, output_channels, 1)

    def forward(self, x):
        out1 = self.depthwise_separable(x)
        out2 = self.standard_conv(x)
        out3 = self.dilated_conv(x)
    # print the size of feature maps
        # print(out1.size())
        # print(out2.size())
        # print(out3.size())
        out = torch.cat([out1, out2, out3], dim=1)
    # reduce the channel size with pointwise convolution
        out = self.pointwise(out)
        return out

class Mixed_5b(nn.Module):

    def __init__(self):
        super(Mixed_5b, self).__init__()

        self.branch0 = DepthSeperabelConv2d(192, 96, kernel_size=1, stride=1)

        self.branch1 = nn.Sequential(
            DepthSeperabelConv2d(192, 48, kernel_size=1, stride=1),
            DepthSeperabelConv2d(48, 64, kernel_size=5, stride=1, padding=2)
        )

        self.branch2 = nn.Sequential(
            DepthSeperabelConv2d(192, 64, kernel_size=1, stride=1),
            DepthSeperabelConv2d(64, 96, kernel_size=3, stride=1, padding=1),
            DepthSeperabelConv2d(96, 96, kernel_size=3, stride=1, padding=1)
        )

        self.branch3 = nn.Sequential(
            nn.AvgPool2d(3, stride=1, padding=1, count_include_pad=False),
            DepthSeperabelConv2d(192, 64, kernel_size=1, stride=1)
        )

    def forward(self, x):
        x0 = self.branch0(x)
        x1 = self.branch1(x)
        x2 = self.branch2(x)
        x3 = self.branch3(x)
        out = torch.cat((x0, x1, x2, x3), 1)
        return out


class Block35(nn.Module):

    def __init__(self, scale=1.0):
        super(Block35, self).__init__()

        self.scale = scale

        self.branch0 = DepthSeperabelConv2d(320, 32, kernel_size=1, stride=1)

        self.branch1 = nn.Sequential(
            DepthSeperabelConv2d(320, 32, kernel_size=1, stride=1),
            DepthSeperabelConv2d(32, 32, kernel_size=3, stride=1, padding=1)
        )

        self.branch2 = nn.Sequential(
            DepthSeperabelConv2d(320, 32, kernel_size=1, stride=1),
            DepthSeperabelConv2d(32, 48, kernel_size=3, stride=1, padding=1),
            DepthSeperabelConv2d(48, 64, kernel_size=3, stride=1, padding=1)
        )

        self.conv2d = nn.Conv2d(128, 320, kernel_size=1, stride=1)
        self.relu = nn.ReLU(inplace=False)

    def forward(self, x):
        x0 = self.branch0(x)
        x1 = self.branch1(x)
        x2 = self.branch2(x)
        out = torch.cat((x0, x1, x2), 1)
        out = self.conv2d(out)
        out = out * self.scale + x
        out = self.relu(out)
        return out


class Mixed_6a(nn.Module):

    def __init__(self):
        super(Mixed_6a, self).__init__()

        self.branch0 = DepthSeperabelConv2d(320, 384, kernel_size=3, stride=2)

        self.branch1 = nn.Sequential(
            DepthSeperabelConv2d(320, 256, kernel_size=1, stride=1),
            DepthSeperabelConv2d(256, 256, kernel_size=3, stride=1, padding=1),
            DepthSeperabelConv2d(256, 384, kernel_size=3, stride=2)
        )

        self.branch2 = nn.MaxPool2d(3, stride=2)

    def forward(self, x):
        x0 = self.branch0(x)
        x1 = self.branch1(x)
        x2 = self.branch2(x)
        out = torch.cat((x0, x1, x2), 1)
        return out


class Block17(nn.Module):

    def __init__(self, scale=1.0):
        super(Block17, self).__init__()

        self.scale = scale

        self.branch0 = DepthSeperabelConv2d(1088, 192, kernel_size=1, stride=1)

        self.branch1 = nn.Sequential(
            DepthSeperabelConv2d(1088, 128, kernel_size=1, stride=1),
            DepthSeperabelConv2d(128, 160, kernel_size=(1,7), stride=1, padding=(0,3)),
            DepthSeperabelConv2d(160, 192, kernel_size=(7,1), stride=1, padding=(3,0))
        )

        self.conv2d = nn.Conv2d(384, 1088, kernel_size=1, stride=1)
        self.relu = nn.ReLU(inplace=False)

    def forward(self, x):
        x0 = self.branch0(x)
        x1 = self.branch1(x)
        out = torch.cat((x0, x1), 1)
        out = self.conv2d(out)
        out = out * self.scale + x
        out = self.relu(out)
        return out


class Mixed_7a(nn.Module):

    def __init__(self):
        super(Mixed_7a, self).__init__()

        self.branch0 = nn.Sequential(
            DepthSeperabelConv2d(1088, 256, kernel_size=1, stride=1),
            DepthSeperabelConv2d(256, 384, kernel_size=3, stride=2)
        )

        self.branch1 = nn.Sequential(
            DepthSeperabelConv2d(1088, 256, kernel_size=1, stride=1),
            DepthSeperabelConv2d(256, 288, kernel_size=3, stride=2)
        )

        self.branch2 = nn.Sequential(
            DepthSeperabelConv2d(1088, 256, kernel_size=1, stride=1),
            DepthSeperabelConv2d(256, 288, kernel_size=3, stride=1, padding=1),
            DepthSeperabelConv2d(288, 320, kernel_size=3, stride=2)
        )

        self.branch3 = nn.MaxPool2d(3, stride=2)

    def forward(self, x):
        x0 = self.branch0(x)
        x1 = self.branch1(x)
        x2 = self.branch2(x)
        x3 = self.branch3(x)
        out = torch.cat((x0, x1, x2, x3), 1)
        return out


class Block8(nn.Module):

    def __init__(self, scale=1.0, noReLU=False):
        super(Block8, self).__init__()

        self.scale = scale
        self.noReLU = noReLU

        self.branch0 = DepthSeperabelConv2d(2080, 192, kernel_size=1, stride=1)

        self.branch1 = nn.Sequential(
            DepthSeperabelConv2d(2080, 192, kernel_size=1, stride=1),
            DepthSeperabelConv2d(192, 224, kernel_size=(1,3), stride=1, padding=(0,1)),
            DepthSeperabelConv2d(224, 256, kernel_size=(3,1), stride=1, padding=(1,0))
        )

        self.conv2d = nn.Conv2d(448, 2080, kernel_size=1, stride=1)
        if not self.noReLU:
            self.relu = nn.ReLU(inplace=False)

    def forward(self, x):
        x0 = self.branch0(x)
        x1 = self.branch1(x)
        out = torch.cat((x0, x1), 1)
        out = self.conv2d(out)
        out = out * self.scale + x
        if not self.noReLU:
            out = self.relu(out)
        return out


class Mix-InResNet(nn.Module):

    def __init__(self, num_classes=102):

        super(Mix-InResNet, self).__init__()
        # Special attributs
        self.input_space = None
        self.input_size = (256, 256, 3)
        self.mean = None
        self.std = None
        # Modules
        self.conv2d_1a = MixedConv2d(3, 32, kernel_size=3, stride=2)
        self.conv2d_2a = MixedConv2d(32, 32, kernel_size=3, stride=1)
        self.conv2d_2b = MixedConv2d(32, 64, kernel_size=3, stride=1)
        self.maxpool_3a = nn.MaxPool2d(3, stride=2)
        self.conv2d_3b = BasicConv2d(64, 80, kernel_size=1, stride=1)
        self.conv2d_4a = MixedConv2d(80, 192, kernel_size=3, stride=1)
        self.maxpool_5a = nn.MaxPool2d(3, stride=2)
        self.mixed_5b = Mixed_5b()
        self.repeat = nn.Sequential(
            Block35(scale=0.17),
            Block35(scale=0.17),
            Block35(scale=0.17),
            Block35(scale=0.17),
            Block35(scale=0.17),
            Block35(scale=0.17),
            Block35(scale=0.17),
            Block35(scale=0.17),
            Block35(scale=0.17),
            Block35(scale=0.17)
        )
        self.mixed_6a = Mixed_6a()
        self.repeat_1 = nn.Sequential(
            Block17(scale=0.10),
            Block17(scale=0.10),
            Block17(scale=0.10),
            Block17(scale=0.10),
            Block17(scale=0.10),
            Block17(scale=0.10),
            Block17(scale=0.10),
            Block17(scale=0.10),
            Block17(scale=0.10),
            Block17(scale=0.10),
            Block17(scale=0.10),
            Block17(scale=0.10),
            Block17(scale=0.10),
            Block17(scale=0.10),
            Block17(scale=0.10),
            Block17(scale=0.10),
            Block17(scale=0.10),
            Block17(scale=0.10),
            Block17(scale=0.10),
            Block17(scale=0.10)
        )
        self.mixed_7a = Mixed_7a()
        self.repeat_2 = nn.Sequential(
            Block8(scale=0.20),
            Block8(scale=0.20),
            Block8(scale=0.20),
            Block8(scale=0.20),
            Block8(scale=0.20),
            Block8(scale=0.20),
            Block8(scale=0.20),
            Block8(scale=0.20),
            Block8(scale=0.20)
        )
        self.block8 = Block8(noReLU=True)
        self.conv2d_7b = BasicConv2d(2080, 1536, kernel_size=1, stride=1)
        self.avgpool_1a = nn.AvgPool2d(6, count_include_pad=False)
        self.last_linear = nn.Linear(1536, num_classes)

    def features(self, input):
        x = self.conv2d_1a(input)
        x = self.conv2d_2a(x)
        x = self.conv2d_2b(x)
        x = self.maxpool_3a(x)
        x = self.conv2d_3b(x)
        x = self.conv2d_4a(x)
        x = self.maxpool_5a(x)
        x = self.mixed_5b(x)
        x = self.repeat(x)
        x = self.mixed_6a(x)
        x = self.repeat_1(x)
        x = self.mixed_7a(x)
        x = self.repeat_2(x)
        x = self.block8(x)
        x = self.conv2d_7b(x)

        return x


    def logits(self, features):
        x = self.avgpool_1a(features)
        x = x.view(x.size(0), -1)
        x = self.last_linear(x)
        return x

    def forward(self, input):
        x = self.features(input)
        x = self.logits(x)
        return x

def inception_resnet_v2():
    return Mix-InResNet()

# model=Mix-InResNet(3)
# print(model)
# inputs=torch.ones([2,3,256,256])
# output=model(inputs)