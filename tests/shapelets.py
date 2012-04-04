#!/usr/bin/env python

# 
# LSST Data Management System
# Copyright 2008, 2009, 2010 LSST Corporation.
# 
# This product includes software developed by the
# LSST Project (http://www.lsst.org/).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the LSST License Statement and 
# the GNU General Public License along with this program.  If not, 
# see <http://www.lsstcorp.org/LegalNotices/>.
#

"""
Tests for math.shapelets

Run with:
   ./shapelets.py
or
   python
   >>> import shapelets; shapelets.run()
"""

import unittest
import numpy

import lsst.utils.tests as utilsTests
import lsst.pex.exceptions
import lsst.afw.geom as geom
import lsst.afw.geom.ellipses as ellipses
import lsst.afw.math.shapelets as shapelets
import lsst.afw.image
import lsst.afw.detection

numpy.random.seed(5)
numpy.set_printoptions(linewidth=120)

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class ShapeletTestMixin(object):

    def assertClose(self, a, b, rtol=1E-5, atol=1E-8):
        self.assert_(numpy.allclose(a, b, rtol=rtol, atol=atol), "\n%s\n!=\n%s" % (a, b))

    def makeImage(self, function, x, y):
        z = numpy.zeros((y.size, x.size), dtype=float)
        e = function.evaluate()
        for i, py in enumerate(y):
            for j, px in enumerate(x):
                z[i,j] = e(float(px), float(py))
        return z

    def measureMoments(self, function, x, y, z):
        gx, gy = numpy.meshgrid(x, y)
        m = z.sum()
        dipole = geom.Point2D((gx * z).sum() / m, (gy * z).sum() / m)
        gx -= dipole.getX()
        gy -= dipole.getY()
        quadrupole = ellipses.Quadrupole(
            (gx**2 * z).sum() / m,
            (gy**2 * z).sum() / m,
            (gx * gy * z).sum() / m
            )
        imageMoments = ellipses.Ellipse(quadrupole, dipole)
        shapeletMoments = function.evaluate().computeMoments()
        self.assertClose(imageMoments.getCenter().getX(), shapeletMoments.getCenter().getX(),
                         rtol=1E-4, atol=1E-3)
        self.assertClose(imageMoments.getCenter().getY(), shapeletMoments.getCenter().getY(),
                         rtol=1E-4, atol=1E-3)
        self.assertClose(imageMoments.getCore().getIXX(), shapeletMoments.getCore().getIXX(),
                         rtol=1E-4, atol=1E-3)
        self.assertClose(imageMoments.getCore().getIYY(), shapeletMoments.getCore().getIYY(),
                         rtol=1E-4, atol=1E-3)
        self.assertClose(imageMoments.getCore().getIXY(), shapeletMoments.getCore().getIXY(),
                         rtol=1E-4, atol=1E-3)
        integral = numpy.trapz(numpy.trapz(z, gx, axis=1), y, axis=0)
        self.assertClose(integral, function.evaluate().integrate(), rtol=1E-3, atol=1E-2)

class ShapeletTestCase(unittest.TestCase, ShapeletTestMixin):

    def setUp(self):
        order = 4
        self.ellipse = ellipses.Ellipse(ellipses.Axes(1.2, 0.8, 0.3), geom.Point2D(0.12, -0.08))
        self.coefficients = numpy.random.randn(shapelets.computeSize(order))
        self.x = numpy.random.randn(25)
        self.y = numpy.random.randn(25)
        self.bases = [
            shapelets.BasisEvaluator(order, shapelets.HERMITE),
            shapelets.BasisEvaluator(order, shapelets.LAGUERRE),
            ]
        self.functions = [
            shapelets.ShapeletFunction(order, shapelets.HERMITE, self.coefficients),
            shapelets.ShapeletFunction(order, shapelets.LAGUERRE, self.coefficients),
            ]
        for function in self.functions:
            function.setEllipse(self.ellipse)

    def testConversion(self):
        for basis, function in zip(self.bases, self.functions):
            evaluator = function.evaluate()
            v = numpy.zeros(self.coefficients.shape, dtype=float)
            t = self.ellipse.getGridTransform()
            for x, y in zip(self.x, self.y):
                basis.fillEvaluation(v, t(geom.Point2D(x, y)))
                p1 = evaluator(x, y)
                p2 = numpy.dot(v, self.coefficients)
                self.assertClose(p1, p2)
            v = numpy.zeros(self.coefficients.shape, dtype=float)
            basis.fillIntegration(v)
            v /= t.getLinear().computeDeterminant()
            p1 = evaluator.integrate()
            p2 = numpy.dot(v, self.coefficients)
            self.assertClose(p1, p2)

    def testMoments(self):
        x = numpy.linspace(-15, 15, 151)
        y = x
        for function in self.functions:
            z = self.makeImage(function, x, y)
            self.measureMoments(function, x, y, z)

    def testDerivatives(self):
        eps = 1E-7
        v = numpy.zeros(self.coefficients.shape, dtype=float)
        v_lo = numpy.zeros(self.coefficients.shape, dtype=float)
        v_hi = numpy.zeros(self.coefficients.shape, dtype=float)
        dx_a = numpy.zeros(self.coefficients.shape, dtype=float)
        dy_a = numpy.zeros(self.coefficients.shape, dtype=float)
        for basis in self.bases:
            for x, y in zip(self.x, self.y):
                basis.fillEvaluation(v, x, y, dx_a, dy_a)
                basis.fillEvaluation(v_hi, x+eps, y) 
                basis.fillEvaluation(v_lo, x-eps, y)
                dx_n = 0.5 * (v_hi - v_lo) / eps
                basis.fillEvaluation(v_hi, x, y+eps) 
                basis.fillEvaluation(v_lo, x, y-eps)
                dy_n = 0.5 * (v_hi - v_lo) / eps
                self.assertClose(dx_n, dx_a, rtol=2.0*eps)
                self.assertClose(dy_n, dy_a, rtol=2.0*eps)
                
class MultiShapeletTestCase(unittest.TestCase, ShapeletTestMixin):

    def testMoments(self):
        x = numpy.linspace(-50, 50, 1001)
        y = x
        elements = []
        for n in range(3):
            ellipse = ellipses.Ellipse(
                ellipses.Axes(
                    float(numpy.random.uniform(low=1, high=2)),
                    float(numpy.random.uniform(low=1, high=2)),
                    float(numpy.random.uniform(low=0, high=numpy.pi))
                    ),
                geom.Point2D(0.23, -0.15)
                )
            coefficients = numpy.random.randn(shapelets.computeSize(n))
            element = shapelets.ShapeletFunction(n, shapelets.HERMITE, coefficients)
            element.setEllipse(ellipse)
            elements.append(element)
        function = shapelets.MultiShapeletFunction(elements)
        x = numpy.linspace(-10, 10, 101)
        y = x
        z = self.makeImage(function, x, y)
        self.measureMoments(function, x, y, z)
    

class ModelBuilderTestCase(unittest.TestCase, ShapeletTestMixin):

    def buildDesignMatrix(self, region, ellipse):
        design = numpy.zeros((shapelets.computeSize(self.order), region.getArea()), dtype=float).transpose()
        evaluator = shapelets.BasisEvaluator(self.order, shapelets.HERMITE)
        n = 0
        gt = ellipse.getGridTransform()
        for span in region.getSpans():
            y = span.getY()
            for x in range(span.getX0(), span.getX1() + 1):
                p = gt(geom.Point2D(x, y))
                evaluator.fillEvaluation(design[n,:], p)
                n += 1
        return design

    def buildNumericalDerivative(self, builder, parameters, makeEllipse):
        eps = 1E-6
        derivative = numpy.zeros((len(parameters), shapelets.computeSize(self.order),
                                  builder.getRegion().getArea()), dtype=float).transpose()
        for i in range(len(parameters)):
            parameters[i] += eps
            ellipse = makeEllipse(parameters)
            builder.update(ellipse)
            derivative[:,:,i] = builder.getDesignMatrix()
            parameters[i] -= 2.0 * eps
            ellipse = makeEllipse(parameters)
            builder.update(ellipse)
            derivative[:,:,i] -= builder.getDesignMatrix()
            derivative[:,:,i] /= 2.0 * eps
        return derivative

    def setUp(self):
        self.order = 3
        self.ellipse = ellipses.Ellipse(ellipses.Axes(10, 7, 0.3), geom.Point2D(500, 600))
        self.bbox = geom.Box2I(lsst.afw.geom.Point2I(480, 580), geom.Point2I(501, 601))
        rEllipse = ellipses.Ellipse(self.ellipse)
        rEllipse.scale(4)
        self.inputRegion = lsst.afw.detection.Footprint(rEllipse)
        self.inputMask = lsst.afw.image.MaskU(self.bbox)
        self.varianceImage = lsst.afw.image.ImageF(self.bbox)
        imageShape = self.inputMask.getArray().shape
        self.inputMask.getArray()[:,:] |= (numpy.random.randn(*imageShape) > 1.5) # sprinkle in bad pixels
        self.varianceImage.getArray()[:,:] = numpy.random.randn(*imageShape)**2 + 1.0
        self.maskedRegion = lsst.afw.detection.Footprint(self.inputRegion)
        self.maskedRegion.intersectMask(self.inputMask, 0x1)
        self.clippedRegion = lsst.afw.detection.Footprint(self.inputRegion)
        self.clippedRegion.clipTo(self.bbox)
        self.maskedDesign = self.buildDesignMatrix(self.maskedRegion, self.ellipse)
        self.clippedDesign = self.buildDesignMatrix(self.clippedRegion, self.ellipse)
        maskedVariance = numpy.zeros(self.maskedRegion.getArea(), dtype=numpy.float32)
        clippedVariance = numpy.zeros(self.clippedRegion.getArea(), dtype=numpy.float32)
        lsst.afw.detection.flattenArray(self.maskedRegion, self.varianceImage.getArray(), maskedVariance,
                                        self.bbox.getMin())
        lsst.afw.detection.flattenArray(self.clippedRegion, self.varianceImage.getArray(), clippedVariance,
                                        self.bbox.getMin())
        self.maskedWeights = 1.0 / maskedVariance**0.5
        self.clippedWeights = 1.0 / clippedVariance**0.5

    def tearDown(self):
        del self.ellipse
        del self.bbox
        del self.inputRegion
        del self.inputMask
        del self.maskedRegion
        del self.clippedRegion
        del self.varianceImage

    def check(self, builder, region, design):
        self.assertEqual(builder.getRegion().getArea(), region.getArea())
        self.assertClose(builder.getDesignMatrix(), design)

    def doImageTest(self, ImageClass):
        image = ImageClass(self.bbox)
        builder = shapelets.ModelBuilder(self.order, self.ellipse, self.inputRegion, image)
        self.check(builder, self.clippedRegion, self.clippedDesign)

    def doMaskedImageTest(self, ImageClass, MaskedImageClass):
        image = ImageClass(self.bbox)
        mi = MaskedImageClass(image, self.inputMask, self.varianceImage)
        builder = shapelets.ModelBuilder(self.order, self.ellipse, self.inputRegion, mi, 0x1, False)
        self.check(builder, self.maskedRegion, self.maskedDesign)
        builder = shapelets.ModelBuilder(self.order, self.ellipse, self.inputRegion, mi, 0x1, True)
        self.check(builder, self.maskedRegion, self.maskedDesign * self.maskedWeights[:,numpy.newaxis])
        builder = shapelets.ModelBuilder(self.order, self.ellipse, self.inputRegion, mi, 0x0, False)
        self.check(builder, self.clippedRegion, self.clippedDesign)
        builder = shapelets.ModelBuilder(self.order, self.ellipse, self.inputRegion, mi, 0x0, True)
        self.check(builder, self.clippedRegion, self.clippedDesign * self.clippedWeights[:,numpy.newaxis])

    def testImageF(self):
        self.doImageTest(lsst.afw.image.ImageF)
        
    def testMaskedImageF(self):
        self.doMaskedImageTest(lsst.afw.image.ImageF, lsst.afw.image.MaskedImageF)

    def testImageD(self):
        self.doImageTest(lsst.afw.image.ImageD)
        
    def testMaskedImageD(self):
        self.doMaskedImageTest(lsst.afw.image.ImageD, lsst.afw.image.MaskedImageD)

    def testDerivative1(self):
        """test derivative with no reparameterization"""
        image = lsst.afw.image.ImageD(self.bbox)
        builder = shapelets.ModelBuilder(self.order, self.ellipse, self.inputRegion, image)
        a = numpy.zeros((5, shapelets.computeSize(self.order), builder.getRegion().getArea()),
                         dtype=float).transpose()
        builder.computeDerivative(a)
        def makeAxesEllipse(p):
            return ellipses.Ellipse(ellipses.Axes(*p[0:3]), geom.Point2D(*p[3:5]))
        n = self.buildNumericalDerivative(builder, self.ellipse.getParameterVector(), makeAxesEllipse)
        # no hard requirement for tolerances here, but I've dialed them to the max to avoid regressions
        self.assertClose(a, n, rtol=1E-4, atol=1E-6)

    def testDerivative2(self):
        """test derivative with trivial reparameterization (derivative wrt center point only)"""
        image = lsst.afw.image.ImageD(self.bbox)
        builder = shapelets.ModelBuilder(self.order, self.ellipse, self.inputRegion, image)
        jac = numpy.zeros((5, 2), dtype=float)
        jac[3,0] = 1.0
        jac[4,1] = 1.0
        a = numpy.zeros((2, shapelets.computeSize(self.order), builder.getRegion().getArea()),
                         dtype=float).transpose()
        builder.computeDerivative(a, jac)
        def makePoint(p):
            return ellipses.Ellipse(self.ellipse.getCore(), geom.Point2D(*p))
        n = self.buildNumericalDerivative(builder, self.ellipse.getParameterVector()[3:5], makePoint)
        # no hard requirement for tolerances here, but I've dialed them to the max to avoid regressions
        self.assertClose(a, n, rtol=1E-4, atol=1E-6)

    def testDerivative3(self):
        """test derivative with nontrivial reparameterization (derivative wrt different core)"""
        image = lsst.afw.image.ImageD(self.bbox)
        builder = shapelets.ModelBuilder(self.order, self.ellipse, self.inputRegion, image)
        quad = ellipses.Quadrupole(self.ellipse.getCore())
        jac = numpy.zeros((5, 3), dtype=float)
        jac[:3,:] = self.ellipse.getCore().dAssign(quad)
        a = numpy.zeros((3, shapelets.computeSize(self.order), builder.getRegion().getArea()),
                         dtype=float).transpose()
        builder.computeDerivative(a, jac)
        def makeQuadrupole(p):
            return ellipses.Ellipse(ellipses.Quadrupole(*p), self.ellipse.getCenter())
        n = self.buildNumericalDerivative(builder, quad.getParameterVector(), makeQuadrupole)
        # no hard requirement for tolerances here, but I've dialed them to the max to avoid regressions
        self.assertClose(a, n, rtol=1E-4, atol=1E-6)


#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def suite():
    """Returns a suite containing all the test cases in this module."""

    utilsTests.init()

    suites = []
    suites += unittest.makeSuite(ShapeletTestCase)
    suites += unittest.makeSuite(MultiShapeletTestCase)
    suites += unittest.makeSuite(ModelBuilderTestCase)
    suites += unittest.makeSuite(utilsTests.MemoryTestCase)
    return unittest.TestSuite(suites)

def run(shouldExit=False):
    """Run the tests"""
    utilsTests.run(suite(), shouldExit)

if __name__ == "__main__":
    run(True)
